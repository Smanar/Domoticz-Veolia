# Veolia Plugin
#
# Author: Smanar 2026
#
#
#
"""
<plugin key="Veolia" name="Veolia Plugin" author="Samanar" version="1.0.0">
    <params>
        <param field="Username" label="E-mail" width="140px" required="true" default="a.b@c.com"/>
        <param field="Password" label="Pasword" width="140px" required="true" default="1234567"/>
        <param field="Mode1" label="Mode" width="150px">
            <options>
                <option label="Normal" value="0"  default="true" />
                <option label="RESET" value="1"/>
            </options>
        </param>
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Debug info Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic+Messages" value="126"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections+Python" value="18"/>
                <option label="Connections+Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""

import DomoticzEx as Domoticz

import urllib, time, configparser, os
from datetime import datetime, date, timedelta

try:
    import simplejson as json
except ImportError:
    import json

REQUESTPRESENT = True
try:
    import requests
except:
    REQUESTPRESENT = False

# FIXED
LOGIN_URL = "cognito-idp.eu-west-3.amazonaws.com"
BACKEND_ISTEFR = "prd-ael-sirius-backend.istefr.fr"
CLIENT_ID = "3kghade1fg54739kj8pkbova8j"
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'

PortalURL = ["eau.veolia.fr", "eaudetm.monespace.eau.veolia.fr"]
PortalClient = ["3kghade1fg54739kj8pkbova8j", "19bjc8ldefie683n889iiubjc8"]

GlobalHeaders = { 'Content-Type': 'text/xml; charset=utf-8', \
                  'Connection': 'keep-alive', \
                  'Accept': '*/*', \
                  'User-Agent': UA}


WATER_COUNTER = 1
FRONT = 'WEB_ORDINATEUR'
MAX_REQUEST = 2

#STEP
LOGIN = 1
ACCOUNT = 2
BILLING = 3
DATA = 4
WAITING = 5

class BasePlugin:

    httpServerConn = None
    Mail = ''
    Pass = ''
    dtNextRefresh = 0
    Portal = 0
    Token = ''
    lastlogin = datetime.now()
    id_abonnement = ""
    id_tiers =  ""
    id_contact = ""
    id_compteur = ""
    id_numeroPDS = ""
    id_debut_abonnement = ""
    NextRequest = 0
    MaxRequest = 0
    Flood = datetime.now()

    config = configparser.ConfigParser()


    def __init__(self):
        self.isStarted = False
        return

    def onStart(self):
        if Parameters["Mode6"] != "0":
            Domoticz.Debugging(int(Parameters["Mode6"]))
        Domoticz.Debugging(144)

        self.Mail = Parameters["Username"]
        self.Pass = Parameters["Password"]

        if not self.Mail or not self.Pass:
            Domoticz.Error("Settings not completed")
            return

        try:
            self.Portal = int(Parameters["Mode1"])
        except:
            self.Portal = 0

        if self.Portal == 1:
            Domoticz.Status("Reset register data")
            os.remove(Parameters["HomeFolder"]+"UserData.ini")
            return

        #To force the firt request
        self.dtNextRefresh = datetime(2002, 12, 31)

        #Create widget
        self.CreateIfnotExist("General", WATER_COUNTER)

        #Loas Userdata
        self.LoadUserData()

        #Init startup sequence
        self.NextRequest = LOGIN

    def onStop(self):
        Domoticz.Debug("onStop called")
        if self.httpServerConns:
            self.httpServerConns.Disconnect()

    def onConnect(self, Connection, Status, Description):
        if (Status == 0):
            Domoticz.Debug("Connected successfully to: " + Connection.Address)

            sendData = None

            headers = GlobalHeaders.copy()
            headers['Host'] = Connection.Address

            if Connection.Name == "Login":
                Domoticz.Debug("Login")

                _json = {
                    "ClientId": CLIENT_ID,
                    "AuthFlow": "USER_PASSWORD_AUTH",
                    "AuthParameters": {"USERNAME": self.Mail, "PASSWORD": self.Pass},
                }

                _json = json.dumps(_json)
                _json = _json.replace (' ','')

                headers['Content-Type'] = 'application/x-amz-json-1.1'
                headers['x-amz-target'] = 'AWSCognitoIdentityProviderService.InitiateAuth'
                headers['Content-Length'] = str(len(_json))

                sendData = { 'Verb' : 'POST',
                             'URL'  : '/',
                             'Headers' : headers,
                             'Data' : _json
                           }

                self.lastlogin = datetime.now()

            elif Connection.Name == "GetAccount":
                Domoticz.Debug("GetAccount")

                headers['Authorization'] = 'Bearer '  + self.Token
                #headers['Cache-Control'] = "no-cache"

                url = '/espace-client?type-front=' + FRONT

                sendData = { 'Verb' : 'GET',
                             'URL'  : url,
                             'Headers' : headers
                           }

            elif Connection.Name == "GetFacturation":
                Domoticz.Debug("GetFacturation")

                headers['Authorization'] = 'Bearer '  + self.Token

                url = "/abonnements/" + str(self.id_abonnement) + "/facturation"

                sendData = { 'Verb' : 'GET',
                             'URL'  : url,
                             'Headers' : headers
                           }


            elif Connection.Name == "Getvalue":
                Domoticz.Debug("Getvalue")

                #On repars 3 jours en arriere
                current_date = date.today() - timedelta(days=3)
                current_year = current_date.year
                current_month = current_date.month

                _param = {
                    "annee": current_year,
                    "numero-pds": self.id_numeroPDS,
                    "date-debut-abonnement": self.id_debut_abonnement,
                    "mois" : current_month
                }

                headers['Authorization'] = 'Bearer '  + self.Token

                url = '/consommations/' + str(self.id_abonnement) + '/journalieres'

                #_param not working on Domoticz ?
                import urllib.parse
                url = url + '?' + urllib.parse.urlencode(_param)

                sendData = { 'Verb' : 'GET',
                             'URL'  : url,
                             'Headers' : headers
                           }

            if sendData:
                Connection.Send(sendData)

        else:
            Domoticz.Debug("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description)

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage called for connection: " + Connection.Name)
        Domoticz.Debug(Data)
        strData = Data["Data"].decode("utf-8", "ignore")
        Status = int(Data["Status"])

        if (Status == 200):
            if Connection.Name == "Login":
                try:
                    j = json.loads(strData)
                    self.Token = j['AuthenticationResult']['AccessToken']
                    expiration = datetime.now() + timedelta(seconds=j['AuthenticationResult']['ExpiresIn'])

                    Domoticz.Status("Got Token")

                    self.NextRequest = ACCOUNT
                    self.MaxRequest = 0

                except:
                    Domoticz.Error("Can't login on Veolia site")

            if Connection.Name == "GetAccount":
                try:
                    j = json.loads(strData)
                    self.id_abonnement = j['contacts'][0]['tiers'][0]['abonnements'][0]['id_abonnement']
                    self.id_tiers =  j['contacts'][0]['tiers'][0]['id']
                    self.id_contact = j['contacts'][0]['id_contact']
                    self.id_compteur = j['contacts'][0]['tiers'][0]['abonnements'][0]['numero_compteur']

                    Domoticz.Status("Got acoount data")
                    self.SaveUserData()

                    self.NextRequest = BILLING
                    self.MaxRequest = 0

                except:
                    Domoticz.Error("Can't retreive account data from Veolia site")

            if Connection.Name == "GetFacturation":
                try:
                    j = json.loads(strData)
                    self.id_numeroPDS = j['numero_pds']
                    self.id_debut_abonnement = j['date_debut_abonnement']

                    Domoticz.Status("Got billing data")
                    self.SaveUserData()

                    self.NextRequest = DATA
                    self.MaxRequest = 0

                except:
                    Domoticz.Error("Can't retreive account data from Veolia site")

            if Connection.Name == "Getvalue":
                try:
                    j = json.loads(strData)

                    #Domoticz.Status(str(j))
                    Domoticz.Status("Got values")
                    self.MaxRequest = 0

                    #Program next update
                    dtNow = datetime.now()
                    self.dtNextRefresh = setRefreshTime(dtNow)
                    Domoticz.Status("Next Update : " + str(self.dtNextRefresh))
                    self.NextRequest = WAITING

                    n = len(j)
                    for v in j:
                        n -= 1
                        index = int(v['index']['litre'])
                        date = v['date_releve']
                        comsumption = int(v['consommation']['litre'])

                        if n < 3:

                            data = str(index) + ";" + str(comsumption)

                            #Update dashboard but only if there is a change with the last value
                            if n == 0:
                                Domoticz.Status("Last value used for widget > " + str(date) + " " + str(index))
                                UpdateDevice("General", WATER_COUNTER,{'nValue': 0, 'sValue': data})

                            #Update logs for 3 lasts values
                            data = data + ";" + str(date)
                            UpdateDevice("General", WATER_COUNTER,{'nValue': 0, 'sValue': data})

                except:
                    Domoticz.Error("Can't retreive value from Veolia site")

        else:
            if (Status == 403) and (datetime.now() - self.lastlogin > timedelta(seconds = 3600)):
                    Domoticz.Debug("Token expired, reconnecting")
                    self.UpdateLogin()
            else:
                Domoticz.Error("Returned a status: " + str(Status))

        self.httpServerConn.Disconnect()

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called for connection '"+Connection.Name+"'.")

    def onHeartbeat(self):
        #Missing requierement ?
        if self.NextRequest == LOGIN:
            self.UpdateLogin()
        elif self.NextRequest == ACCOUNT:
            self.UpdateAccount()
        elif self.NextRequest == BILLING:
            self.UpdateFacturation()
        elif self.NextRequest == DATA:
            self.UpdateValue()

        dtNow = datetime.now()

        #Domoticz.Status(str(self.NextRequest) + " " + str(self.dtNextRefresh - dtNow))

        #Normal poll
        if self.NextRequest == WAITING:
            if dtNow > self.dtNextRefresh:
                #Trigger a new complete phase
                self.NextRequest = LOGIN

        #Anti flood
        if self.MaxRequest > MAX_REQUEST and dtNow > self.Flood:
            self.MaxRequest = 0
            self.Flood = dtNow

    def onCommand(self, DeviceID, Unit, Command, Level, Hue):
        pass

    def CreateIfnotExist(self, __IEEE, devicetype):
        if (__IEEE not in Devices) or (devicetype not in Devices[__IEEE].Units):
            CreateDevice(__IEEE, devicetype)

    def Request(self, name, address):

        if self.httpServerConn and (self.httpServerConn.Connecting() or self.httpServerConn.Connected()):
            Domoticz.Error("Already connected")
            return

        if  self.MaxRequest >= MAX_REQUEST:
            if datetime.now() > self.Flood:
                Domoticz.Error("Requests blocked for 1 hour, too much request for connection: " + name)
                self.Flood = datetime.now() + timedelta(hours=1)
            return

        self.MaxRequest += 1

        self.httpServerConn = Domoticz.Connection(Name=name, Transport="TCP/IP", Protocol="HTTPS", Address=address, Port="443")
        self.httpServerConn.Connect()
        return

    def UpdateLogin(self):
        if True:#not self.Token:
            Domoticz.Status("Updating Token")
            self.Request("Login", LOGIN_URL)
        else:
            self.NextRequest = ACCOUNT
        return

    def UpdateAccount(self):
        if True:#not self.id_abonnement or not self.id_tiers or not self.id_contact or not self.id_compteur:
            Domoticz.Status("Updating account data")
            self.Request("GetAccount", BACKEND_ISTEFR)
        else:
            Domoticz.Status("Account data in date")
            self.NextRequest = BILLING
        return

    def UpdateFacturation(self):
        if True:#not self.id_numeroPDS or not self.id_debut_abonnement:
            Domoticz.Status("Updating billing data")
            self.Request("GetFacturation", BACKEND_ISTEFR)
        else:
            Domoticz.Status("Billing data in date")
            self.NextRequest = DATA
        return

    def UpdateValue(self): 
        Domoticz.Status("Updating Veolia values")
        self.Request("Getvalue", BACKEND_ISTEFR)
        return

    def SaveUserData(self):
        self.config['DEFAULT']['id_abonnement'] = str(self.id_abonnement)
        self.config['DEFAULT']['id_tiers'] = str(self.id_tiers)
        self.config['DEFAULT']['id_contact'] = str(self.id_contact)
        self.config['DEFAULT']['id_compteur'] = str(self.id_compteur)
        self.config['DEFAULT']['id_numeroPDS'] = str(self.id_numeroPDS)
        self.config['DEFAULT']['id_debut_abonnement'] = str(self.id_debut_abonnement)

        with open(Parameters["HomeFolder"]+"UserData.ini", 'w') as configfile:
            self.config.write(configfile)

        Domoticz.Status("User Data Saved")

    def LoadUserData(self):
        try :
            self.config.read(Parameters["HomeFolder"]+"UserData.ini")

            self.id_abonnement = self.config['DEFAULT']['id_abonnement']
            self.id_tiers = self.config['DEFAULT']['id_tiers']
            self.id_contact = self.config['DEFAULT']['id_contact']
            self.id_compteur = self.config['DEFAULT']['id_compteur']
            self.id_numeroPDS = self.config['DEFAULT']['id_numeroPDS']
            self.id_debut_abonnement = self.config['DEFAULT']['id_debut_abonnement']
            Domoticz.Status("User Data Loaded")

        except:
            Domoticz.Status("No User Data available")



global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def onCommand(DeviceID, Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Hue)

# Generic helper functions
def UpdateDevice(IEEE, devicetype, kwarg):

    #Update the device
    NeedUpdate = False
    for a in kwarg:
        if kwarg[a] != getattr(Devices[IEEE].Units[devicetype], a ):
            NeedUpdate = True
            break

    #force update, at least 1 every 24h
    if not NeedUpdate:
        LUpdate = Devices[IEEE].Units[devicetype].LastUpdate
        LUpdate=time.mktime(time.strptime(LUpdate,"%Y-%m-%d %H:%M:%S"))
        current = time.time()
        if (current-LUpdate) > 86400:
            NeedUpdate = True

    if NeedUpdate:
        Domoticz.Debug("### Update device ("+Devices[IEEE].Units[devicetype].Name+") : " + str(kwarg))
        Devices[IEEE].Units[devicetype].nValue = kwarg['nValue']
        Devices[IEEE].Units[devicetype].sValue = kwarg['sValue']
        Devices[IEEE].Units[devicetype].Update(Log=True)
    else:
        Domoticz.Debug("### Update device ("+Devices[IEEE].Units[devicetype].Name+") : " + str(kwarg) + ", IGNORED , no changes !")


def CreateDevice(IEEE, devicetype):
    kwarg = {}

    Unit = devicetype
    Name = IEEE + '-' + str(devicetype)

    if devicetype == WATER_COUNTER:
        kwarg['Type'] = 243
        kwarg['Subtype'] = 33
        kwarg['Switchtype'] = 2
        #kwarg['Image'] = 11

    kwarg['DeviceID'] = IEEE
    kwarg['Name'] = Name
    kwarg['Unit'] = Unit
    myUnit = Domoticz.Unit(**kwarg)
    myUnit.Create()

    Domoticz.Status("### Create Device " + IEEE + " > " + Name + ' as Unit ' + str(Unit) )

def setRefreshTime(dtDate=None):
    if dtDate is None:
        dtDate = datetime.now()
    return dtDate + timedelta(days=1)
