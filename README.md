# Deepwork with Deepseek

Block distractive sites for a specific duration. 


Create a new conda environment from environment.yml
```
conda env create -f environment.yml
```

Activate the newly created environment
```
conda activate dwd 
```

Change permissions to make the script executable 
```
chmod +x blocker.py
```

Choose to block with various different time units
```
sudo python blocker.py -t 30s  # 30 seconds
sudo python blocker.py -t 45m  # 45 minutes
sudo python blocker.py -t 2h   # 2 hours
sudo python blocker.py -t 1d   # 1 day
sudo python blocker.py -t 45   # 45 minutes (default unit)
```

