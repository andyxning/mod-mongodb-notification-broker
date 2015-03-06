## mod-mongodb-notification-broker
This module is used by Broker daemon to relay **All Notification Log Broks** 
to a mongoDB database.  
This module is mainly used to store Notification infos to do some analysis or 
make reports later.

## Notications  
There are two main problems if the database can not be connected and db(update,
 find) operations can not be accomplished:  
* if db(update, find) operations can not be accomplished due to mongodb is
down or network problems, it will reconnect until db operation succeeds.
* we store all the Notification broks in a queue, if the queue is full(in case 
of problem one, we reconnect all the time and do not consume the queued broks.),
we just ignore the new inserted broks.

## SetUp
Note: Replica set MongoDB instances is the recommended way to work with.  

### Replica Set  

##### MongoDB Replica Set with three instances
* host1:port1
* host2:port2
* host3:port3  

##### MongoDB Replica Set configuration
* [with authenticate](http://docs.mongodb.org/manual/tutorial/deploy-replica-set-with-auth/)
* [without authenticate](http://docs.mongodb.org/manual/tutorial/deploy-replica-set/)

##### Configuration in mongodb-notification-broker.cfg
> module_name     mongodb-notification-broker    
> module_type     mongodb_notification_broker    
> retry_per_log   5   
> queue_size      20000  
> high_availability     true   
> replica_set       host1:port1, host2:port2, host3:port3  
> url_options     w=1&wtimeoutMS=3000&journal=true&readPreference=secondary&replicaSet=shinken&connectTimeoutMS=3000    
> database     shinken_broker_notification  
> username     shinken_broker_notification  
> password     shinken_broker_notification  

### Stand alone

##### MongoDB Stand alone
* host:port

##### Configuration in mongodb-notification-broker.cfg
> module_name     mongodb_notification_broker  
> module_type     mongodb_notification_broker  
> retry_per_log   5    
> queue_size      20000   
> high_availability     false   
> stand_alone   host:port   
> url_options     w=1&wtimeoutMS=3000&journal=true&readPreference=secondary&replicaSet=shinken&connectTimeoutMS=3000  
> database     shinken_broker_notification  
> username     shinken_broker_notification  
> password     shinken_broker_notification  