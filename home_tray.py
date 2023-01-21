import wx.adv
import wx.svg
import wx
import os.path
import requests
import json
import sched
import time
from _thread import start_new_thread
from homeassistant_api import Client
import configparser

def get_icon_path(icon_name, state):
    icon_path = "icons/"+icon_name.replace(":", "-")+"-"+state+".svg"
    if os.path.isfile(icon_path):
        return icon_path
    else:
        return "icons/default-"+state+".svg"

def create_menu_item(menu, label, func):
    item = wx.MenuItem(menu, -1, label)
    menu.Bind(wx.EVT_MENU, func, id=item.GetId())
    menu.Append(item)
    return item

class TaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame, entity_id, client):
        super(TaskBarIcon, self).__init__()
        self.frame = frame
        self.entity_id = entity_id
        self.client = client

        self.scheduler = sched.scheduler(time.time, time.sleep)
        def update_task(scheduler): 
            self.update_state()
            self.scheduled_event = self.scheduler.enter(5, 1, update_task, (scheduler,))
        self.scheduled_event = self.scheduler.enter(5, 1, update_task, (self.scheduler,))
        start_new_thread(self.scheduler.run, ())

        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)
        # self.Bind(wx.adv.EVT_TASKBAR_RIGHT_DOWN, self.on_right_down)

        self.update_state()

    def update_state(self):
        entity = self.client.get_entity(entity_id=self.entity_id)
        entity_state = entity.state.state
        entity_icon = entity.state.attributes["icon"] if "icon" in entity.state.attributes else "default"
        entity_name = entity.state.attributes["friendly_name"]

        # if entity_state == "on":
        #     if "rgb_color" in entity.state.attributes:
        #         rgb_color = entity.state.attributes["rgb_color"]
        #     else:
        #         rgb_color = [253, 213, 27]
        # else:
        #     rgb_color = [0, 0, 0] # or [225, 225, 225]
        # TODO: change color of SVG or bitmap accordingly

        icon = get_icon_path(entity_icon, entity_state)
        self.set_icon(icon, entity_name)
        self.state = entity_state

    def set_icon(self, icon_path, tooltip):
        svg = wx.svg.SVGimage.CreateFromFile(icon_path)
        icon = svg.ConvertToScaledBitmap(wx.Size(30, 30))
        self.SetIcon(icon, tooltip)

    def on_left_down(self, event):
        self.update_state()
        light = self.client.get_domain('homeassistant')
        light.toggle(entity_id=self.entity_id)
        print(self.entity_id, "toggle")
        time.sleep(0.1)
        self.update_state()

    def CreatePopupMenu(self):
        menu = wx.Menu()
        create_menu_item(menu, 'Exit', self.on_exit)
        return menu

    def cleanup(self):
        if self.scheduled_event:
            try:
                self.scheduler.cancel(self.scheduled_event)
            except:
                pass

        self.RemoveIcon()
        self.frame.Close()
        wx.CallAfter(self.Destroy)

    def on_exit(self, event):
        wx.Exit()

def ask(parent=None, message='', default_value=''):
    dlg = wx.TextEntryDialog(parent, message, caption="Initial Setup", value=default_value)
    dlg.ShowModal()
    result = dlg.GetValue()
    dlg.Destroy()
    return result

class App(wx.App):
    def OnInit(self):
        # init GUI
        self.frame = wx.Frame(None)
        self.SetTopWindow(self.frame)

        # load config
        config = configparser.ConfigParser()
        domains = ""
        domain_entities_ignore = ""
        try:
            config.read('config.ini')
            token = config['HASS']['Token']
            api_url = config['HASS']['ApiUrl']
            entities = config['HASS']['Entities']
            if config.has_option('HASS', 'Domains'):
                domains = config['HASS']['Domains']
            if config.has_option('HASS', 'DomainEntitiesIgnore'):
                domain_entities_ignore = config['HASS']['DomainEntitiesIgnore']
        except KeyError:
            config['HASS'] = {}
            token = config['HASS']['Token'] = ask(message='Please enter your Home Assistant Long-Lived Access Token. You can generate it at https://my.home-assistant.io/redirect/profile/.')
            api_url = config['HASS']['ApiUrl'] = ask(message='Please enter Home Assistant API Url. It should look something like this: http://192.168.0.125:8123/api')
            entities = config['HASS']['Entities'] = ask(message='Please enter the IDs (seperated by a comma) of the entities you like to add.')
            with open('config.ini', 'w') as configfile:
                config.write(configfile)

        entities = [x for x in entities.split(',') if x != '']
        domains = [x for x in domains.split(',') if x != '']
        domain_entities_ignore = [x for x in domain_entities_ignore.split(',') if x != '']
        
        # init hass client
        client = Client(api_url, token, cache_session=False)

        # init tray icons
        self.tray_icons = []
        for domain in domains:
            for entity in client.get_entities()[domain].entities:
                full_id = f"{domain}.{entity}"
                if full_id in domain_entities_ignore or full_id in entities:
                    continue

                self.tray_icons.append(TaskBarIcon(self.frame, full_id, client))

        for entity in entities:
            self.tray_icons.append(TaskBarIcon(self.frame, entity, client))

        return True

    def OnExit(self):
        for tray_icon in self.tray_icons:
            tray_icon.cleanup()
        
        return 0

def main():
    app = App(False)
    app.MainLoop()


if __name__ == '__main__':
    main()
