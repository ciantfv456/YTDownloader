import csv
import uvicorn
from pytube import YouTube
from fastapi import FastAPI, APIRouter, Response
from starlette.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from multiprocessing import Process
from uuid import uuid4
from pathlib import Path

download_router = APIRouter()
token_router = APIRouter()
app = FastAPI(docs_url='/docs')

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VIDEO_DOWNLOAD_DIR = "Downloads/videos"
AUDIO_DOWNLOAD_DIR = "Downloads/audio"
DOWNLOADS_LIST = "download_list.txt"

downloads = {}

class Download:
    # {token}-{status}-{data}
    def __init__(self, content: str):
        self.token, self.status, self.location = content.strip('\n').split('-')
    def __str__(self) -> str:
        return f'{self.token}-{self.status}-{self.location}\n'
    def __repr__(self) -> str:
        return f'{self.token}-{self.status}-{self.location}\n'


def get_download(token: str):
    with open(DOWNLOADS_LIST, 'r') as f:
        tokens = f.readlines()
        download_list = list(filter(lambda content: content.startswith(token), tokens))
        return Download(download_list[0]) if download_list else None


def set_download(download: Download):
    with open(DOWNLOADS_LIST, 'r') as f:
        # {token}-{status}-{data}
        content = f.readlines()
    with open(DOWNLOADS_LIST, 'w') as f:
        for i, _downloads in enumerate(content):
            if download:
                d = Download(_downloads)
                if d.token == download.token:
                    content[i] = str(download)
                    break
        f.writelines(content)


def new_download(download: Download):
    with open(DOWNLOADS_LIST, 'a') as f:
        f.writelines([str(download)])


def delete_download(token):
    with open(DOWNLOADS_LIST, 'r') as f:
        lines = f.readlines()
    with open(DOWNLOADS_LIST, 'w') as f:
        for line in lines:
            if not line.startswith(token):
                f.write(line)


def YoutubeAudioDownload(video_url: str, token: str):
    download = get_download(token)
    try:
        video = YouTube(video_url)
        audio = video.streams.filter(only_audio = True).first()
        audio.download(AUDIO_DOWNLOAD_DIR, filename=f'{token}.mp3')
        download.location = Path(AUDIO_DOWNLOAD_DIR) / f'{token}.mp3'
        download.status = "finidhed"
        set_download(download)
    except:
        print("Failed to download audio")
        download.status = "error"
        set_download(download)

    print("audio was downloaded successfully")


def YoutubeVideoDownload(video_url: str, token: str):
    download = get_download(token)
    try:
        video = YouTube(video_url)
        video = video.streams.get_highest_resolution()
        video.download(VIDEO_DOWNLOAD_DIR, filename=f'{token}.mp4')
        download.location = Path(VIDEO_DOWNLOAD_DIR) / f'{token}.mp4'
        download.status = "finidhed"
        set_download(download)
    except:
        print("Unable to download video at this time!")

    print("Video downloaded!")


@token_router.get('/status/{token}')
async def get_status(token: str):
    try:
        download = get_download(token)
        return Response(download.status) if download else Response(status_code=404)
    except:
        return Response(status_code=404)


@token_router.get('/file/{token}')
async def get_file(token: str):
    download = get_download(token)
    if not download.location:
        message = "still downloading file" if download.status == 'downloading' else "Couldn't download file"
        return Response(message, status_code=500)
    loc = Path(download.location)
    return FileResponse(Path(download.location), media_type='application/octet-stream', filename=loc.name)


@token_router.delete('/{token}')
async def delete_token(token: str):
    if token in downloads:
        downloads[token]['process'].terminate()
        downloads.pop(token)
    delete_download(token)


@download_router.post("/video")
async def YoutubeVideo(url: str):
    try:
        token = uuid4().hex
        download = f'{token}-downloading-'
        new_download(download)
        downloads[token] = {'status': 'downloading', 'process': None}
        downloads[token]['process'] = Process(name=token, target=YoutubeVideoDownload, kwargs={"video_url": url, "token": token})
        downloads[token]['process'].start()
        return JSONResponse({"token": token}, status_code=200)
    except Exception as err:
        print(err)
        downloads.pop(token)
        return Response(str(err), status_code=500)


@download_router.post("/audio")
async def YoutubeAudio(url: str):
    try:
        token = uuid4().hex
        download = f'{token}-downloading-'
        new_download(download)
        downloads['token'] = {'status': 'downloading', 'process': None}
        downloads['token']['process'] = Process(target=YoutubeAudioDownload, kwargs={"video_url": url, "token": token})
        downloads['token']['process'].start()
        return JSONResponse({"token": token}, status_code=200)
    except Exception as err:
        downloads.pop(token)
        return Response(str(err), status_code=500)

app.include_router(token_router, prefix='/token')
app.include_router(download_router, prefix='/download')

if __name__ == '__main__':
    uvicorn.run(app)