# Domoticz-Veolia, a plugin to retrieve the Veolia water meter readings and use them in Domoticz

## Description

This plugin works with a 3-day delay to be sure having data, because Veolia don't work in real time.
The plugin retreive data for the complete month (less 3 day), so don't worry if you miss a day, it will be updated later.

## Installation.
- With command line, go to your plugins directory (domoticz/plugins).   
- Run:   
```git clone https://github.com/Smanar/Domoticz-Veolia.git```
- (If needed) Make the plugin.py file executable:   
```chmod +x Domoticz-Veolia/plugin.py```
- Restart Domoticz.   
- Enable the plugin in hardware page (hardware page, select Veolia plugin, click "update").   

You can later update the plugin
- With command line, go to the plugin directory (domoticz/plugin/Domoticz-Veolia).   
- Run:   
```git pull```
- Restart Domoticz.    

To test the beta branch :
```
git pull
git checkout beta
git pull
```
