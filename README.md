# search_freeplane

Script to parse and search Freeplane MindMap XML files. 

The benefit of this tool compared to just searching with tools like `grep` is that this tool will flatten the XML within the mindmap and will search the entire node and its subchildren. 

Script has been tested on mindmap files of type `standard-1.6.mm` generated from Freeplane though other Freeplane mindmap template should also be supported. 

## Pre-requisites

Files that are searched by default should have `.mm` extension which is used by default by Freeplane.

## Setup

### Via docker
```
docker build -t search_freeplane:latest .
```

### Via virtualenv
```
python3 -m virtualenv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
deactivate
```

### Setup 

Once installed via either methods above, it is easier to setup an alias in the `~/.bashrc` OR `~/.bash_profile` to quickly run searches in common locations e.g. as shown below
```
# Added to ~/.bash_profile
search_maps() {
    docker run --rm -v /opt/my-maps:/opt/my-maps -it -e "TERM=xterm-256color" --rm search_freeplane -k "$1" -f /opt/my-maps
}

# Now search for `.*hello` regex in folder `/opt/my-maps`
search_maps ".*hello.*"
```

## Usage

To search for the keyword `pcageneral` in all mindmap files (`.mm`) in folder `~/my-maps`, execute the following command:
```
python3 main.py -k pcageneral -f ~/my-maps
```

To apply case sensitivity when searching, use `-c`:
```
python3 main.py -k pcageneral -f ~/my-maps
``` 

To display matches ignoring the newlines in the output and search for regex `.*hello.*world.*` in flattend mindmap (new lines will get replaced by `\n`)
```
python3 main.py -k `hello.*world`  -f ~/my-maps -rn
```

To run the same command above from docker container
```
docker run --rm -v /opt/my-maps:/opt/my-maps -it -e "TERM=xterm-256color" --rm search_freeplane -k "pcageneral" -rn
```