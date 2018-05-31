from winreg import ConnectRegistry, OpenKey, HKEY_LOCAL_MACHINE, EnumValue
from PIL import Image
from io import BytesIO
import re, os, json, requests, hashlib, win32serviceutil, appinfo
steam_header_base = "https://steamcdn-a.akamaihd.net/steam/apps/"

def importVRManifest():
    app = []
    manifest = json.load(open(steamPath + r"\config\steamapps.vrmanifest"))
    for index in manifest["applications"]:
        temp = []
        temp.append(getAppid(index["app_key"]))
        temp.append(index["strings"]["en_us"]["name"])
        temp.append(index["url"])
        print("Found Installed VR Game: " + temp[1])
        app.append(temp)
    addGameFolder(app)
    return app

def findPath(RegKeyLoc, index, tupleIndex):
    reg = ConnectRegistry(None,HKEY_LOCAL_MACHINE)
    key = OpenKey(reg, RegKeyLoc)
    return EnumValue(key, index)[tupleIndex] #contains path

def getAppid(file):
    return re.search(r"(\d+)", file)[0]

def addGameFolder(appids):
    with open(steamPath + "//steamapps//libraryfolders.vdf") as a:
        #add directories of steam games
        folder = [steamPath]
        for dir in re.findall(r"[A-Z]:.+y", a.read()):
            folder.append(dir)
        #Find appmanifests (useful for appids) and Build partial directory name
        for dir in folder:
            appidFolder = dict([])
            for file in os.listdir(dir + "\\steamapps\\"):
                 if file.endswith(".acf"):
                    appidFolder[file[12:-4]] = ""
            for index, appid in appidFolder.items():
                appidFolder[index] = r"{}\steamapps\common\{}".format(dir,appid[12:-4])
        #Finish directory name
        with open(steamPath + "//appcache//appinfo.vdf",'rb') as f:
            vdf = appinfo.load(f)
            for appid in appids:
                installKey = vdf[int(appid[0])]["sections"][b"appinfo"][b"config"][b"installdir"]
                execKey = vdf[int(appid[0])]["sections"][b"appinfo"][b"config"][b"launch"]
                installdir = installKey
                for keys in execKey.keys():
                    try:
                        #Look for executable with type vr and windows (incase of linux)
                        if execKey[keys][b"type"] == b'vr':
                            exec = execKey[keys][b"executable"]
                    except KeyError:
                        #Default to first key
                        exec = execKey[b"0"][b"executable"]
                completePath = "{}/{}".format(installdir.decode(),exec.decode())
                completePath = appidFolder[appid[0]] + completePath
                completePath = re.sub(r"(:\\\\)|(\\\\)|(\\)|[:/]", '_', completePath).replace(".exe","").replace(" ","")#Ugly af
                appid.append(completePath)

def createManifest(info):
    json_game = json.load(open("game_template.json"))
    displayName = info[1]
    canonicalName = info[3]
    print("Creating manifest for {}".format(info[1]))
    manifestFolder = oculusPath + r"CoreData\\Manifests\\" + canonicalName + ".json"
    json_game["canonicalName"] = canonicalName
    json_game["displayName"] = displayName
    #Keeping file to steam because in case, haven't tested removing it
    json_game["files"][steamPath + "\\steam.exe"] = "" 
    json_game["launchFile"] = "cmd.exe"
    json_game["launchParameters"] = "/c start " + info[2]
    with open(manifestFolder, "w") as f:
        json.dump(json_game, f)

def sha256(img):
    with open(img, 'rb') as f:
        h = hashlib.sha256(f.read())
        return h.hexdigest()

def createAssetManifest(info):
    #Retrieve base img
    response = requests.get(steam_header_base + info[0] + "/header.jpg")
    img = response.content
    canonicalName = info[3] + '_assets'
    assetFolder = oculusPath + "\\CoreData\\Software\\StoreAssets\\" + canonicalName
    manifestFolder = oculusPath + r"CoreData\\Manifests\\" + canonicalName + ".json"
    print("Creating images for {}".format(info[1]))
    #Check if folder exists
    if not os.path.exists(assetFolder):
        os.makedirs(assetFolder)
    #Save all images in their respective folders
    imgBase = Image.open(BytesIO(img))
    #Landscape
    imgLand = imgBase.resize((360,202), Image.ANTIALIAS)
    imgLand.save(assetFolder + r"\cover_landscape_image.jpg")
    #Square
    imgSquare = imgBase.resize((360,202), Image.ANTIALIAS)
    imgSquare.save(assetFolder + r"\cover_square_image.jpg")
    #Icon
    imgIcon = imgBase.resize((192,192), Image.ANTIALIAS)
    imgIcon.save(assetFolder + r"\icon_image.jpg")
    #Original
    imgOrg = imgBase.resize((256,256), Image.ANTIALIAS)
    imgOrg.save(assetFolder + r"\original.png")
    #Small Landscape
    imgSmall = imgBase.resize((270,90), Image.ANTIALIAS)
    imgSmall.save(assetFolder + r"\small_landscape_image.jpg")
    #Transparent, reuse
    imgLand.save(assetFolder + r"\logo_transparent_image.png")
    #Get SHA256 of all the files
    hexLand = sha256(assetFolder + r"\cover_landscape_image.jpg")
    hexSquare = sha256(assetFolder + r"\cover_square_image.jpg")
    hexIcon = sha256(assetFolder + r"\icon_image.jpg")
    hexOrg = sha256(assetFolder + r"\original.png")
    hexSmall = sha256(assetFolder + r"\small_landscape_image.jpg")
    #Create asset manifest
    json_game_asset = json.load(open("game_assets_template.json"))
    json_game_asset["files"]["cover_landscape_image.jpg"] = hexLand
    json_game_asset["files"]["cover_landscape_image_large.jpg"] = hexOrg
    json_game_asset["files"]["cover_square_image.jpg"] = hexSquare
    json_game_asset["files"]["icon_image.jpg"] = hexIcon
    json_game_asset["files"]["small_landscape_image.jpg"] = hexSmall
    #Land is the same as Transparent
    json_game_asset["files"]["logo_transparent_image.png"] = hexLand
    json_game_asset["canonicalName"] = canonicalName
    #Store json asset file
    with open(manifestFolder, "w") as f:
        json.dump(json_game_asset, f)

#Main
steamPath = findPath(r"SOFTWARE\WOW6432Node\Valve\Steam",1,1)
oculusPath = findPath(r"SOFTWARE\WOW6432Node\Oculus VR, LLC\Oculus",0,1)
vrmanifest = importVRManifest()
print("Creating Manifests")
for appmanifest in vrmanifest:
    createManifest(appmanifest)
    createAssetManifest(appmanifest)
print("Finished creating manifests, restarting oculus service")
#Admin Privileges are needed
service_name = "Oculus VR Runtime Service"
try:
    win32serviceutil.StopService(service_name)
    win32serviceutil.StartService(service_name)
except:
    print("could not stop \'{}\', please restart it manualy".format(service_name))
input('Press Any Key to exit')
