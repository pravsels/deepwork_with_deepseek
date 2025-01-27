# Deepwork with Deepseek

Block distractive sites for a specific duration. 


Change permission to run as root

```
chmod +x blocker.py
```

Choose to block with various different time units. 

```
sudo python blocker.py -f distractions.txt -t 30s  # 30 seconds
sudo python blocker.py -f distractions.txt -t 45m  # 45 minutes
sudo python blocker.py -f distractions.txt -t 2h   # 2 hours
sudo python blocker.py -f distractions.txt -t 1d   # 1 day
sudo python blocker.py -f distractions.txt -t 45   # 45 minutes (default unit)
```

