import json, hashlib, requests, os
from PIL import Image
from io import BytesIO

steam_header_base = "https://steamcdn-a.akamaihd.net/steam/apps/"

def sha256(img):
    with open(img, 'rb') as f:
        h = hashlib.sha256(f.read())
        return h.hexdigest()

#Create Manifest for application
def createManifest(info, oculusPath, steamPath):
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

#Create Manifest for Assets
def createAssetManifest(info, oculusPath, steamPath):
    #Retrieve base img
    response = requests.get(steam_header_base + info["appid"] + "/header.jpg")
    if(response.status_code == 200):
        #Use header from steampage
        imgBase = Image.open(BytesIO(response.content))
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
