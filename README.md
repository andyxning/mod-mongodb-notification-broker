## mod-mongodb-notification-broker
This module is used by Broker daemon to relay **All Notification Log Broks** 
to a mongoDB database.  
This module is mainly used to store Notification infos to do some analysis or 
make reports later.

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

##### Configuration in mongodb-broker.cfg
> module_name     mongodb-notification-broker  
> module_type     mongodb_notification_broker  
> high_availability     true  
> replica_set       host1:port1, host2:port2, host3:port3  
> read_preference   secondary  
> database     shinken_broker_notification  
> username     shinken_broker_notification  
> password     shinken_broker_notification  

### Stand alone

##### MongoDB Stand alone
* host:port

##### Configuration in mongodb-broker.cfg
> module_name     mongodb_notification_broker  
> module_type     mongodb_notification_broker  
> high_availability     false  
> stand_alone   host:port  
> database     shinken_broker_notification  
> username     shinken_broker_notification  
> password     shinken_broker_notification  