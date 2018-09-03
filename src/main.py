from winreg import ConnectRegistry, OpenKey, HKEY_LOCAL_MACHINE, EnumValue #Finding install location
from steamfiles import appinfo
from createManifest import createAssetManifest, createManifest
import json, re, os, traceback, win32serviceutil

def findPath(RegKeyLoc, index, tupleIndex):
    reg = ConnectRegistry(None,HKEY_LOCAL_MACHINE)
    key = OpenKey(reg, RegKeyLoc)
    return EnumValue(key, index)[tupleIndex] #contains path

steamPath = findPath(r"SOFTWARE\WOW6432Node\Valve\Steam",1,1)
oculusPath = findPath(r"SOFTWARE\WOW6432Node\Oculus VR, LLC\Oculus",0,1)

#Contains appid, name, launch(url), path(game path)
def importVRManifest():
    appinfo = []
    #Build appinfo dict
    manifest = json.load(open(steamPath + r"\config\steamapps.vrmanifest"))
    for index in manifest["applications"]:
        appid = {}
        #10 characters from steam.app.
        appid["appid"] = index["app_key"][10:]
        appid["name"] = index["strings"]["en_us"]["name"]
        #Try and get URL, exception handles non-steam vr games
        try:
            appid["launch"] = index["url"]
        except KeyError:
            print("Skipping non-steam VR game (Use Oculus's builtin solution)")
        #add dictionary into array 
        appinfo.append(appid)
    #add remaining locations into dictionary
    fillLocations(appinfo)
    return appinfo

#Determine game folder location from appinfo vdf. Used in an attempt to prevent duplicat
def fillLocations(appids):
    appLoc = appidLocation()
    with open(steamPath + "//appcache//appinfo.vdf",'rb') as f:
        vdf = appinfo.load(f)
        for game in appids:
            try:
                #Steam app
                installdir = vdf[int(game["appid"])]["sections"][b"appinfo"][b"config"][b"installdir"]
                execKey = vdf[int(game["appid"])]["sections"][b"appinfo"][b"config"][b"launch"]
                for keys in execKey.keys():
                    try:
                        #Look for executable with type vr
                        if execKey[keys][b"type"] == b'vr':
                            exec = execKey[keys][b"executable"]
                    except KeyError:
                        #Default to first key
                        exec = execKey[b"0"][b"executable"]
                #Folder + Exe
                completePath = "\{}\{}".format(installdir.decode(),exec.decode())
                #Add install folder to path
                completePath = appLoc[game["appid"]] + completePath
            except KeyError:
                #None steam app
                completePath = game["launch"]
            completePath = re.sub(r"(:\\|\\|_|\.|/)", '_', completePath).replace(' ','').replace("_exe","")#Ugly af
            game["path"] = completePath

def appidLocation():
    pathLocation = dict()
    paths = getPaths()
    #Partial Path (Only Drive location)
    for dir in paths:
        for file in os.listdir(dir + "\\steamapps\\"):
                 if file.endswith(".acf"):
                    #Remove appmanifest from filename
                    pathLocation.update({file[12:-4]: dir + "\\steamapps\\common" })
    return pathLocation

def getPaths():
    folder = [steamPath] #Add steam install location by default
    with open(steamPath + "//steamapps//libraryfolders.vdf") as a:
        for dir in re.findall(r"[A-Z]:.+y", a.read()):
            folder.append(dir.replace("\\\\","\\")) #Directories have \\ so it's more consistent
    return folder

#Main
try:
    vrmanifest = importVRManifest()
    print("Creating Manifests")
    for appmanifest in vrmanifest:
        createManifest(appmanifest, oculusPath, steamPath)
        createAssetManifest(appmanifest, oculusPath, steamPath)
    print("Finished creating manifests, restarting oculus service")
    #Admin Privileges are needed
    service_name = "Oculus VR Runtime Service"
    try:
        win32serviceutil.StopService(service_name)
        win32serviceutil.StartService(service_name)
    except:
        print("could not stop \'{}\', please restart it manualy".format(service_name))
    input('Press Enter to exit')
except Exception as error:
    print("An error has occured, please look at the errorlog.txt file for more information")
    with open("errorlog.txt", 'w') as e:
        e.write(traceback.format_exc())
    input("Press Enter to exit")
