```
 ____         __ _   ____
/ ___| _   _ / _| |_| __ )  _____  __
\___ \| | | | |_| __|  _ \ / _ \ \/ /
 ___) | |_| |  _| |_| |_) | (_) >  <
|____/ \__, |_|  \__|____/ \___/_/\_\
       |___/
```

# Setup

```
pip install uv
```

# Build Wheel

```
./build.sh
```

# Install Wheel

```
./install.sh
```

# Run Client

```
syftbox client --config_path=./config.json --sync_folder=~/Desktop/SyftBox --email=your@email.org --port=8082  --server=http://20.168.10.234:8080
```

# Deploy

This builds the latest source to a wheel and deploys and restarts the server:
http://20.168.10.234:8080

```
./deploy.sh
```

# Dev Mode

Run the server and clients locally in editable mode with:
Server:

```
./server.sh
```

Client1:

```
./madhava.sh
```

Client2:

```
./andrew.sh
```
