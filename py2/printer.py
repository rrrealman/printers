#!/usr/bin/python

import usb.core
import usb.util
import sys
import json
from datetime import datetime
import socket
import requests

class USBPrinter(object):
    def __init__(self, _printer):
        self.printer = _printer
        self.status = {}
        CR, LF, self.ESC = [chr(ch) for ch in [13, 10, 27]] # curses.ascii.CR
        self.CRLF = CR + LF
    
    def PJLCmd(self, PJLCommand):
        cmd = "{1}%-12345X@PJL {2}@PJL {0} {2}{1}%-12345X".format(PJLCommand, self.ESC, self.CRLF)
        print "Request text: \n{0}".format(cmd)
        
        if self.printer.is_kernel_driver_active(0):
            reattach = True 
            self.printer.detach_kernel_driver(0)
        else: reattach = False
        
        print "Bytes sended: {0}".format(self.printer.write(0x1, cmd))#, timeout = 2000
        response = self.printer.read(0x81, size_or_buffer = 1024).tostring()#, timeout = 2000
        print "Response: {0}".format(response)
        usb.util.dispose_resources(self.printer)
        
        if reattach: self.printer.attach_kernel_driver(0)
        
        return response.split(self.CRLF)[1:-1]
    
    def refreshStatus(self):
        #self.PJLCmd("INFO VARIABLES")
        #self.PJLCmd("INFO USTATUS")
        
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        for exceptionNum in xrange(10):
            try:
                infoSuppl = {attrt[0]: attrt[1] for attrt in (attr.split(" = ") for attr in self.PJLCmd("INFO SUPPLIES"))}
                infoStatus = {attrt[0]: attrt[1] for attrt in (attr.split("=") for attr in self.PJLCmd("INFO STATUS"))}
                pagecounter = int(self.PJLCmd("INFO PAGECOUNT")[0])
                break
                print "[+] Printer data read successfully"
            except:
                if exceptionNum == 9: 
                    print "[-] Unable to read printer data"
                    return None
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        self.status["SERIAL_NUMBER"] = infoSuppl["SerialNumber"]
        self.status["NAME"]          = ""
        self.status["MODEL"]         = ""
        self.status["IP_ADDRESS"]    = "" #! usb
        self.status["MAC"]           = "" #! usb
        self.status["PRINTER_MONO"]  = pagecounter # total page count black
        self.status["PRINTER_COLOR"] = -1   # total page count color
        self.status["LEVELK"]        = infoSuppl["PercentRemaining"] #black ink
        self.status["LEVELC"]        = -1
        self.status["LEVELM"]        = -1
        self.status["LEVELY"]        = -1
        self.status["STATUS_CODE"]   = infoStatus["CODE"]
        self.status["Alerts"] = [{
                    "Type":"",
                    "date":"",
                    "message":""}]        
        return self.status

class USBPrinters(object):
    class findDeviceClass(object):
        def __init__(self, classArg):
            self._class = classArg
        def __call__(self, device):
            if device.bDeviceClass == self._class:
                return True
            for cfg in device:
                intf = usb.util.find_descriptor(cfg, bInterfaceClass=self._class)
                if intf is not None:
                    return True
            return False
        
    def __init__(self, _serverURL = "http://192.168.41.62:8080/printer"):
        printerDeviceClass = 7
        self.serverURL = _serverURL
        self.printers = [USBPrinter(printer) for printer in usb.core.find(find_all = True, custom_match = self.findDeviceClass(printerDeviceClass))]
        print "[+] {0} printers were found on host".format(len(self.printers)) if self.printers else "[-] Printers were not found on host"

    def sendReport(self):
        printersStatus = [status for status in (printer.refreshStatus() for printer in self.printers) if status is not None]
        if printersStatus:
            allHostIPs = [addr[4][0] for addr in socket.getaddrinfo(socket.gethostname(), None)] #family, socktype, proto, canonname, sockaddr
            currentDate = datetime.isoformat(datetime.now()) #'2016.03.2810:35:15+0300' !!!
            jsonToSend = {"ip": allHostIPs, "currentDate": currentDate, "printers": printersStatus} #json
            print "[+] JSON to sending: {0}".format(jsonToSend)
            response = requests.post(self.serverURL, json = jsonToSend)
            print response.text
            print ("[+] JSON sended successfully " if response.status_code == 200 else "[-] JSON could not be sended ") + str(response.status_code)
        else: print "[-] JSON won't be sended: Nothing to send"

def main():
    
    printers = USBPrinters()
    printers.sendReport()
    
main()