# -*- coding: utf-8 -*-
# 
# Copyright @ 2015 OPS, Qunar Inc. (qunar.com)
# Author: ning.xie <andy.xning@qunar.com>
# 

import sys
import time
import Queue
from threading import Thread, Event

try:
    from pymongo import MongoReplicaSetClient, MongoClient
    from pymongo.errors import (AutoReconnect, ConnectionFailure, InvalidURI,
                                ConfigurationError)
except ImportError:
    raise Exception('Python binding for MongoDB has not been installed. '
                    'Please install "pymongo" first')
    
from shinken.basemodule import BaseModule
from shinken.log import logger
from shinken.util import to_bool


properties = {
              'daemons': ['broker'],
              'type': 'mongodb-notification-broker',
              'external': False
              }


# called by the plugin manager to get a mongodb_notification_broker instance
def get_instance(mod_conf):
    logger.info('[Mongodb-Notification-Broker] Get a Broker module %s' 
                % mod_conf.get_name())
    instance = MongodbBroker(mod_conf)
    return instance


# Main class
class MongodbBroker(BaseModule):
    
    def __init__(self, mod_conf):
        BaseModule.__init__(self, mod_conf)
        self._parse_conf(mod_conf)
        
        self.queue = Queue.Queue(self.queue_size)
        self.read_event = Event()
        self.conn = None
        # service notification log broks. 
        # ref: service.raise_notification_log_entry
        self.service_notification = ('contact',
                                     'host',
                                     'service_description',
                                     'state',
                                     'command',
                                     'output'
                                     )
        # host notification log broks.
        # ref: host.raise_notification_log_entry
        self.host_notification = ('contact',
                                  'host',
                                  'state',
                                  'command',
                                  'output')
        
        
    def _parse_conf(self, mod_conf):
        logger.debug(mod_conf)
        self.high_availability = to_bool(getattr(mod_conf,
                                                 'high_availability', 'false'))
        if not self.high_availability:
            self.stand_alone = getattr(mod_conf, 'stand_alone', '')
            if not self.stand_alone:
                logger.error('[Mongodb-Notification-Broker] Mongodb is '
                             'configured with high availability be false but '
                             'stand_alone is not configured')
                raise Exception('[Mongodb-Notification-Broker] Configuration '
                                'Error')
        else:
            replica_set_str = getattr(mod_conf, 'replica_set', '')
            self.replica_set = self._get_replica_set(replica_set_str)
        self.database = getattr(mod_conf,
                                'database', 'shinken_notification_broker')
        self.username = getattr(mod_conf,
                                'username', 'shinken_broker_notification')
        self.password = getattr(mod_conf,
                                'password', 'shinken-broker_notification')
        self.url_options = getattr(mod_conf, 'url_options', '')
        try:
            self.retry_per_log = int(getattr(mod_conf, 'retry_per_log'))
        except:
            self.retry_per_log = 1
        try:
            self.queue_size = int(getattr(mod_conf, 'queue_size'))
        except:
            self.queue_size = 10000 
        
        
    def _get_replica_set(self, replica_set_str):
        raw_members = replica_set_str.split(',')
        members = []
        for member in raw_members:
            members.append(member.strip())
        return members        
        
        
    def _get_mongodb_url(self):
        scheme = 'mongodb://'
        db_and_options = '/%s?%s' % (self.database, self.url_options) 
        credential = ':'.join((self.username, '%s@' % self.password))
        if not self.high_availability:
            address = self.stand_alone
            mongodb_url = ''.join((scheme, credential, address, db_and_options))
        else:
            address = ','.join(self.replica_set)
            mongodb_url = ''.join((scheme, credential, address, db_and_options))
        return mongodb_url
        
        
    # Called by Broker to do init work
    def init(self):
        logger.info('[Mongodb-Notification-Broker] Initialization of '
                    'mongodb_notification_broker module')
        mongodb_url = self._get_mongodb_url()
        logger.debug('[Mongodb-Notification-Broker] Mongodb connect url: %s' 
                     % mongodb_url)
        
        if self.conn:
            self.do_stop()
        try:
            if not self.high_availability:
                self.conn = MongoClient(mongodb_url)
            else:
                self.conn = MongoReplicaSetClient(mongodb_url)
        except ConnectionFailure:
            logger.warn('[Mongodb-Notification-Broker] Can not make connection '
                        ' with MongoDB')
            raise
            
        except (InvalidURI, ConfigurationError):
            logger.warn('[Mongodb-Notification-Broker] Mongodb connect url '
                        'error')
            logger.warn('[Mongodb-Notification-Broker] Mongodb connect url: %s' 
                        % mongodb_url)
            raise 
        self._get_collections()
        worker = Thread(target=self._main)
        worker.setDaemon(True)
        worker.start()
        
        
    def _get_collections(self):
        db = self.conn[self.database]
        self.hosts = db['hosts']
        self.services = db['services']
        self.notifications = db['notifications']
    
    
    # Override the same function in basemodule.py
    def do_stop(self):
        self.conn.close()
        self.conn = None
    
    
    # If we are confronted with AutoReconnect Exception, then we should always 
    # retry until the operation succeeds. However, if other exception is thrown,
    # we should ignore the operation and go to next operation.
    def _process_db_operation(self, operation, *param):
        reconnect_start = time.time()
        result = None        
        while True:
            try:
                result = operation(*param)
            except AutoReconnect:
                logger.warn('[Mongodb-Notification-Broker] Update error. ' 
                            'Reconnected last %d seconds' % (time.time() - reconnect_start))
                # avoid to invoke too many write operations
                time.sleep(self.retry_per_log)
            except Exception:
                logger.warn('[Mongodb-Notification-Broker] Update error. '
                            'operation %s, param %s' % (operation, param))
                logger.warn(sys.exc_info()[:-1])
                break
            else:
                break
        return result    
    
    
    # main function to update mongodb database
    def _save(self, ref, ref_identity, notification):
        self._process_db_operation(self.notifications.insert, notification)
        if ref == 'service':
            _id = ','.join((ref_identity.get('host'),
                            ref_identity.get('service_description')))
            cursor = self._process_db_operation(self.services.find,
                                                {'_id': _id})
        elif ref == 'host':
            _id = ref_identity.get('host')
            cursor = self._process_db_operation(self.hosts.find, {'_id': _id})
        
        # if service or host find error, 'cursor' will be None.
        # then we can not make sure that whether specific host or service 
        # exists. In order to not make data be wrong, we stop here.
        if cursor:
            if not cursor.count():
                # if notification insert error, then '_id' will not be in it and we
                # then should ignore the notification.
                ref_identity.setdefault('notification_ids',
                                        [notification.get('_id')] if '_id' in notification else [])
                ref_identity.setdefault('_id', _id)
                
                if ref == 'service':
                    self._process_db_operation(self.services.insert, ref_identity)
                elif ref == 'host':
                    self._process_db_operation(self.hosts.insert, ref_identity)
            else:
                document = cursor[0]
                notification_ids = document.get('notification_ids')
                # if notification insert error, then '_id' will not be in it and we 
                # then should ignore the notification
                if '_id' in notification:
                    notification_ids.append(notification.get('_id'))
                    if ref == 'service':
                        self._process_db_operation(self.services.update,
                                                   {'_id': _id},
                                                   {'$set': {'notification_ids': notification_ids}})
                    elif ref == 'host':
                        self._process_db_operation(self.hosts.update,
                                                   {'_id': _id},
                                                   {'$set': {'notification_ids': notification_ids}})
        else:
            logger.warn('[Mongodb-Notification-Broker] Update notification '
                        'success, link error. Notification id: %s' % _id)
    
    
    # The main function of mongodb_broker
    def _do_loop_turn(self):
        self.read_event.wait()
        try:
            brok = self.queue.get_nowait()
        except Queue.Empty:
            self.read_event.clear()
            return 

        msg = brok.data['log']
        parts = msg.split(':', 1)
        if 'SERVICE' in parts[0]:
            service_identiry, notification = self._process_notification_brok('service',
                                                                             self.service_notification,
                                                                             parts[1])
            self._save('service', service_identiry, notification)
        elif 'HOST' in parts[0]:
            host_identity, notification = self._process_notification_brok('host',
                                                                          self.host_notification,
                                                                          parts[1])
            self._save('host', host_identity, notification)


    def _process_notification_brok(self, ref, keys, notification_info):
        elts = notification_info.split(';', len(keys))
        info_map = dict(zip(keys, elts))
        if ref == 'service':
            ref_identity = {'host': info_map.get('host'),
                            'service_description': info_map.get('service_description')
                            }
        elif ref == 'host':
            ref_identity = {'host': info_map.get('host')}
            
        notification = {'contact': info_map.get('contact'),
                        'command': info_map.get('command'),
                        'output': info_map.get('output')
                        }
        return ref_identity, notification
    
    
    # invoked by Broker daemon
    def manage_brok(self, brok):
        if brok.type == 'log' and 'NOTIFICATION' in brok.data['log']:
            try:
                self.queue.put_nowait(brok)
                if not self.read_event.is_set():
                    self.read_event.set()
            except Queue.Full:
                logger.warn('[Mongodb-Notification-Broker] Queue full. Ignored '
                            'brok: %s' % brok.data)
                
                
    def _main(self):
        logger.debug('[Mongodb-Notification-Broker] Start main function')
        while True:
            self._do_loop_turn()
