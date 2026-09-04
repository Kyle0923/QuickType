# bugcheck
## decode bugcheck ID
> Analyzes a bugcheck code and displays detailed information
```
!analyze -v
!gs
```

# start TCP server
## open a debug server
> Opens a debugging server on the specified port  
> and tell me more
```
.server tcp:port={{port num}}
```

# start PIPE server
## open named pipe debug server
> Opens a debugging server using a named pipe
```
.server tcp:{{pipe name}}
```
