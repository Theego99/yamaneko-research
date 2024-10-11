accuracy threshold under .25 will lead to many false detections but wont miss any animals at a lower frame selection rate

if frame selection rate is lower than 1 every 30 it is recommended that a threshold under .30 is set (.2 ~ .3)

for more accurate recall 1 in 33 frames with a .4 detection threshold can be very efficient but it will take on average around 27~30 seconds for processing each 10s video

1 in 80 frames will result in a ~11s processing time per 10s video but it might miss some animals at a high threshold so anything over .35 is not recommended

