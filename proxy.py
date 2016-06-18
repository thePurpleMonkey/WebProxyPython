#####################################################
#                                                   #
#              HTTP PROXY WITH HTTPS TUNNELING      #
#              Version: 1.1                         #
#              Author: Luu Gia Thuy                 #
#              Modified by: Michael Humphrey        #
#                    github.com/thePurpleMonkey     #
#                                                   #
#####################################################

import thread,socket,logging

#********* CONSTANT VARIABLES *********
BACKLOG = 50			# how many pending connections queue will hold
MAX_DATA_RECV = 999999	# max number of bytes we receive at once
BLACKLIST = []			# just an example. Remove with [""] for no blocking at all.

#******************************************#
#************** MAIN PROGRAM **************#
#******************************************#
def main():
	# Log all messages to proxy.log, and log all non-debug messages to stdout
	logging.basicConfig(format="%(asctime)s.%(msecs)03d - %(levelname)-8s - %(message)s",
						datefmt="%m/%d/%Y %I:%M:%S %p",
						filename="proxy.log",
						filemode="w",
						level=logging.DEBUG)
												
	# define a Handler which writes INFO messages or higher to the sys.stderr
	console = logging.StreamHandler()
	console.setLevel(logging.INFO)
	# set a format which is simpler for console use
	formatter = logging.Formatter('%(levelname)-8s %(message)s')
	# tell the handler to use this format
	console.setFormatter(formatter)
	# add the handler to the root logger
	logging.getLogger('').addHandler(console)

	# check the length of command running
	if (len(sys.argv)<2):
		logging.info("No port given, using :8080 (http-alt)")
		port = 8080
	else:
		port = int(sys.argv[1]) # port from argument

	# Listen on all interfaces
	host = '0.0.0.0'
	
	logging.info("Proxy Server Running on %s:%s", host, port)

	try:
		# create a socket
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		# associate the socket to host and port
		s.bind((host, port))

		# listenning
		s.listen(BACKLOG)
	
	except socket.error, (value, message):
		if s:
			s.close()
		logging.exception("Could not open socket. (%s)", message)
		raise

	# get the connection from client
	while True:
		conn, client_addr = s.accept()

		# create a thread to handle request
		thread.start_new_thread(proxy_thread, (conn, client_addr))
		
	s.close()
#************** END MAIN PROGRAM ***************

#               !!! WARNING !!!
# This function will only format text correctly
# on certain platorms with certain terminal
# emulators. On other platorms text may be
# garbled and unreadable. Specifically, on 
# Windows colors are not shown and the control
# charcters garble the output.
def printout(type,request,address):
	if "Block" in type or "Blacklist" in type:
		colornum = 91
	elif "Request" in type:
		colornum = 92
	elif "Reset" in type:
		colornum = 93

	print "\033[",colornum,"m",address[0],"\t",type,"\t",request,"\033[0m"
	#logging.debug("%s\t%s\t%s", address[0], type, request)


#*******************************************#
#************ FORWARD_DATA FUNC ************#
# A thread to forward data from one socket  #
# to another. NOTE: Data is only forwarded  #
# in one direction. To do two-way           #
# forwarding, call this function twice with #
# its arguments swapped.                    #
# Author: Michael Humphrey                  #
#         github.com/thePurpleMonkey        #
#*******************************************#
def forward_data(_from, to):
	logging.debug("Forwarding %s to %s...", _from.getpeername(), to.getpeername())
	
	try:
		data = _from.recv(MAX_DATA_RECV)
		while data != "":
			to.sendall(data)
			data = _from.recv(MAX_DATA_RECV)
	except socket.error as e:
		_from.close()
		to.close()
		
		if e.errno in (10054, 10053):
			logging.debug("Connection aborted.")
		else:
			logging.exception("Communication error with %s -> %s",_from.getpeername(), to.getpeername())

#************* END FORWARD_DATA ************#
	
#*****************************************#
#********* PROXY_THREAD FUNC *************#
# A thread to handle request from browser #
#*****************************************#
def proxy_thread(conn, client_addr):

	# get the request from browser
	request = conn.recv(MAX_DATA_RECV)

	# parse the first line
	first_line = request.split('\n')[0]
	
	logging.debug("Request: %s", first_line)
	
	# get url
	try:
		verb, url, version = first_line.split(' ')
	except ValueError:
		logging.warning("Received malformed request. Ignorning.")
		conn.close()
		return
	except:
		logging.exception("Failure to parse http request. Client address: %s", client_addr)
		conn.close()
		raise

	for i in range(0,len(BLACKLIST)):
		if BLACKLIST[i] in url:
			#printout("Blacklisted",first_line,client_addr)
			logging.info("Blocked request from %s for %s", client_addr, url)
			conn.close()
			return


	#printout("Request",first_line,client_addr)
	
	# find the webserver and port
	http_pos = url.find("://")		  # find pos of ://
	if (http_pos==-1):
		temp = url
	else:
		temp = url[(http_pos+3):]	   # get the rest of url
	
	port_pos = temp.find(":")		   # find the port pos (if any)

	# find end of web server
	webserver_pos = temp.find("/")
	if webserver_pos == -1:
		webserver_pos = len(temp)
		
		
	webserver = ""
	port = -1
	if (port_pos==-1 or webserver_pos < port_pos):	  # default port
		port = 80
		webserver = temp[:webserver_pos]
	else:	   # specific port
		port = int((temp[(port_pos+1):])[:webserver_pos-port_pos-1])
		webserver = temp[:port_pos]
		
	logging.info("Request from %s to %s:%s", conn.getpeername(), webserver, port)

	if verb.upper() == "CONNECT":
		# Establish HTTP tunnel
		logging.debug("Initiating HTTP tunnel...")
		
		logging.debug("Creating connection to %s:%s...", webserver, port)
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.connect((webserver, port))
		
		logging.debug("Sending HTTP response...")
		conn.send("HTTP/1.1 200 OK\r\n\r\n")
		
		logging.debug("Begin data transmission...")
		thread.start_new_thread(forward_data, (conn, s))
		thread.start_new_thread(forward_data, (s, conn))
		
		
	else:
		# Plain HTTP request
		try:
			# create a socket to connect to the web server
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
			s.connect((webserver, port))
			s.send(request)		 # send request to webserver
			
			while 1:
				# receive data from web server
				data = s.recv(MAX_DATA_RECV)
				
				if (len(data) > 0):
					# send to browser
					conn.send(data)
				else:
					break
			s.close()
			conn.close()
		except socket.error, (value, message):
			if s:
				s.close()
			if conn:
				conn.close()
			#printout("Peer Reset",first_line,client_addr)
			logging.info("Peer reset\t%s\t%s", first_line, client_addr)
			return
#********** END PROXY_THREAD ***********
	
if __name__ == '__main__':
	main()


