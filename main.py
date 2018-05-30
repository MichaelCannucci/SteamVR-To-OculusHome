from winreg import ConnectRegistry, OpenKey, HKEY_LOCAL_MACHINE, EnumValue
from PIL import Image
from io import BytesIO
import re, os, json, requests, hashlib, win32serviceutil
steam_header_base = "https://steamcdn-a.akamaihd.net/steam/apps/"

def importVRManifest():
    app = []
    manifest = json.load(open(steamPath + r"\config\steamapps.vrmanifest"))
    for index in manifest["applications"]:
        temp = []
        temp.append(getAppid(index["app_key"]))
        temp.append(index["strings"]["en_us"]["name"])
        temp.append(index["url"])
        print("found vr game: " + temp[1])
        app.append(temp)
    return app

def findPath(RegKeyLoc, index, tupleIndex):
    reg = ConnectRegistry(None,HKEY_LOCAL_MACHINE)
    key = OpenKey(reg, RegKeyLoc)
    return EnumValue(key, index)[tupleIndex] #contains path

def getAppid(file):
    return re.search(r"(\d+)", file)[0]

def createManifest(item):
    json_game = json.load(open("game_template.json"))
    displayName = item[1]
    canonicalName = ("imported_steam_game_" + item[1]).replace(" ","_").replace(":","")
    manifestFolder = oculusPath + r"CoreData\\Manifests\\" + canonicalName + ".json"
    json_game["canonicalName"] = canonicalName
    json_game["displayName"] = displayName
    #Keeping file to steam because in case, haven't tested removing it
    json_game["files"][steamPath + "\\steam.exe"] = "" 
    json_game["launchFile"] = "cmd.exe"
    json_game["launchParameters"] = "/c start " + item[2]
    with open(manifestFolder, "w") as f:
        json.dump(json_game, f)

def removeImages(folder):
    for image in os.listdir(folder):
        os.remove(folder + '\\' + image)

def sha256(img):
    with open(img, 'rb') as f:
        h = hashlib.sha256(f.read())
        return h.hexdigest()

def createAssetManifest(item):
    #Retrieve base img
    response = requests.get(steam_header_base + item[0] + "/header.jpg")
    img = response.content
    #assets img are encoded in SHA-256
    canonicalName = ("imported_steam_game_" + item[1] + "_assets").replace(" ","_").replace(":","")
    assetFolder = oculusPath + "\\CoreData\\Software\\StoreAssets\\" + canonicalName
    manifestFolder = oculusPath + r"CoreData\\Manifests\\" + canonicalName + ".json"
    print("Creating images for {}".format(item[1]))
    #Check if folder exists
    if os.path.exists(assetFolder):
        removeImages(assetFolder)
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
print("Creating Files for appids in list")
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
input('Press ENTER to exit')