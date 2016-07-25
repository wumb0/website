Title: Quick and Dirty File Transfers with Python
Date: 2014-07-07 21:50
Category: Old Posts
Tags: old
Slug: Quick-and-Dirty-File-Transfers-with-Python
Authors: wumb0

If you ever need to transfer something quickly from one computer (that has Python) to another you can fire up the Python SimpleHTTPServer module to help you out. Simply change directories to the path you want to serve and run:
```bash
python -m SimpleHTTPServer 8080
```
This will serve the current directory via HTTP on port 8080. Download what you need on the other machine then control-C the python server to shut it down and that's it!
The port can be changed from 8080 to any other port but keep in mind that if you want to serve on ports <1024 then you'll need to run the command as root.
Neat!
