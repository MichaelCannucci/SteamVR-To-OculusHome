from winreg import ConnectRegistry, OpenKey, HKEY_LOCAL_MACHINE, EnumValue #Finding install location
from steamfiles import appinfo
from PIL import Image
from io import BytesIO
import json, re, os, hashlib, requests, win32serviceutil, traceback
import win32api, win32con, win32ui, win32gui #Getting icon

def findPath(RegKeyLoc, index, tupleIndex):
    reg = ConnectRegistry(None,HKEY_LOCAL_MACHINE)
    key = OpenKey(reg, RegKeyLoc)
    return EnumValue(key, index)[tupleIndex] #contains path

steamPath = findPath(r"SOFTWARE\WOW6432Node\Valve\Steam",1,1)
oculusPath = findPath(r"SOFTWARE\WOW6432Node\Oculus VR, LLC\Oculus",0,1)
steam_header_base = "https://steamcdn-a.akamaihd.net/steam/apps/"

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
        #Try and get URL, exception handles non-steam vr games (uses binary location)
        try:
            appid["launch"] = index["url"]
        except KeyError:
            #Binary instead of URL launch
            appid["launch"] = index["binary_path_windows"].replace("\\","/")
        #add dictionary into array 
        appinfo.append(appid)
    #add remaining locations into dictionary
    fillLocations(appinfo)
    return appinfo

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

def sha256(img):
    with open(img, 'rb') as f:
        h = hashlib.sha256(f.read())
        return h.hexdigest()

def createManifest(info):
    json_game = json.load(open("src/game_template.json"))
    displayName = info["name"]
    canonicalName = info["path"]
    print("Creating manifest for {}".format(info["name"]))
    manifestFolder = oculusPath + "CoreData\Manifests\\" + canonicalName + ".json"
    json_game["canonicalName"] = canonicalName
    json_game["displayName"] = displayName
    #Keeping file to steam because in case, haven't tested removing it
    json_game["files"][steamPath + "\\steam.exe"] = "" 
    json_game["launchFile"] = "cmd.exe"
    json_game["launchParameters"] = "/c start \"VR\" \"{}\"".format(info["launch"])
    with open(manifestFolder, "w") as f:
        json.dump(json_game, f)

#Used for create manifests
def createHeaderFromIcon(exe):
    gameIcon = get_icon(exe).resize((64,64), Image.ANTIALIAS)
    img_w, img_h = gameIcon.size
    background = Image.new("RGB",(180,101))
    bg_w, bg_h = background.size
    #Place in middle of application
    offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
    background.paste(gameIcon,offset)
    return background

def get_icon(exe):
    #Credits: https://gist.github.com/RonnChyran/7314682
    ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
    ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)
    large, small = win32gui.ExtractIconEx(exe, 0)
    if len(large) == 0:
        return False
    win32gui.DestroyIcon(small[0])
    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
    icon_bmp = win32ui.CreateBitmap()
    icon_bmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
    hdc = hdc.CreateCompatibleDC()
    hdc.SelectObject(icon_bmp)
    hdc.DrawIcon((0,0), large[0]) #draw the icon before getting bits
    icon_info = icon_bmp.GetInfo()
    icon_buffer = icon_bmp.GetBitmapBits(True)
    icon = Image.frombuffer('RGB', (icon_info['bmWidth'], icon_info['bmHeight']), icon_buffer, 'raw', 'BGRX', 0, 1)
    win32gui.DestroyIcon(large[0])
    return icon 

def createAssetManifest(info):
    #Retrieve base img
    response = requests.get(steam_header_base + info["appid"] + "/header.jpg")
    if(response.status_code == 200):
        #Use header from steampage
        imgBase = Image.open(BytesIO(response.content))
    else:
        imgBase = createHeaderFromIcon(info["path"])
    canonicalName = info["path"] + '_assets'
    assetFolder = oculusPath + "\\CoreData\\Software\\StoreAssets\\" + canonicalName
    manifestFolder = oculusPath + r"CoreData\\Manifests\\" + canonicalName + ".json"
    print("Creating images for {}".format(info["name"]))
    #Check if folder exists
    if not os.path.exists(assetFolder):
        os.makedirs(assetFolder)
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
    json_game_asset = json.load(open("src/game_assets_template.json"))
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
try:
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
    input('Press Enter to exit')
except Exception as error:
    print("An error has occured, please look at the errorlog.txt file for more information")
    with open("errorlog.txt", 'w') as e:
        e.write(traceback.format_exc())
    input("Press Enter to exit")
