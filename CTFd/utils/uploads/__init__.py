import shutil
import patoolib
import posixpath
import os
from werkzeug.utils import secure_filename

from flask import current_app

from CTFd.models import ChallengeFiles, Files, PageFiles, db, AnticheatFlags
from CTFd.utils import get_app_config
from CTFd.utils.uploads.uploaders import FilesystemUploader, S3Uploader
from CTFd.utils.encoding import hexencode

UPLOADERS = {"filesystem": FilesystemUploader, "s3": S3Uploader}


def get_uploader():
    return UPLOADERS.get(get_app_config("UPLOAD_PROVIDER") or "filesystem")()

def flags_upload(*args, **kwargs):
    f = kwargs.get("file")
    flags = f.read().decode().strip().replace("\r", "").split()
    challenge_id = kwargs.get("challenge_id") or kwargs.get("challenge")
    for i, flag in enumerate(flags):
        anticheat_flag = AnticheatFlags(
            content = flag,
            task_id = challenge_id,
            user_id = i + 1
            )
        db.session.add(anticheat_flag)
    db.session.commit()

def multiple_upload(*args, **kwargs):
    base_path = current_app.config.get("UPLOAD_FOLDER")
    location = os.path.join(base_path, kwargs.get("file").filename)
    challenge_id = kwargs.get("challenge_id") or kwargs.get("challenge")
    with open(location, "wb") as dst:
        shutil.copyfileobj(kwargs.get("file"), dst, 16384)
    taskDir = posixpath.join(base_path, str(challenge_id))
    try:
        os.mkdir(taskDir)
    except:
        pass
    uploadedFiles = []
    try:
        patoolib.extract_archive(location, outdir=taskDir)
    except:
        print("Can't unpack!!!")
        os.remove(location)
        return []
    
    try:
        os.remove(location)
        model = ChallengeFiles
        model_args = {"type": "challenge", "location": None}

        # Сохранение файлов для каждой команды/пользователя в зависимости от режима соревнования
        for address, _ , files in os.walk(taskDir):
            for concreteFile in files:
                participant_id = os.path.split(address)[1]
                filename = secure_filename(concreteFile)
                md5hash = hexencode(os.urandom(16))
                file_path = posixpath.join(md5hash, filename)
                location = os.path.join(base_path, file_path)
                directory = os.path.dirname(location)
                if not os.path.exists(directory):
                    os.makedirs(directory)
                shutil.move(os.path.join(address, concreteFile), location)
                model_args = {"type": "challenge", "location": file_path, "participant": participant_id, "challenge_id" : challenge_id}
                file_row = model(**model_args)
                uploadedFiles.append(file_row)
                db.session.add(file_row)
            db.session.commit()
    except:
        shutil.rmtree(taskDir)

    shutil.rmtree(taskDir)
    return uploadedFiles

def upload_file(*args, **kwargs):
    file_obj = kwargs.get("file")
    challenge_id = kwargs.get("challenge_id") or kwargs.get("challenge")
    page_id = kwargs.get("page_id") or kwargs.get("page")
    file_type = kwargs.get("type", "standard")

    model_args = {"type": file_type, "location": None}
    model = Files
    if file_type == "challenge":
        model = ChallengeFiles
        model_args["challenge_id"] = challenge_id
    if file_type == "page":
        model = PageFiles
        model_args["page_id"] = page_id

    uploader = get_uploader()
    location = uploader.upload(file_obj=file_obj, filename=file_obj.filename)

    model_args["location"] = location

    file_row = model(**model_args)
    db.session.add(file_row)
    db.session.commit()
    return file_row


def delete_file(file_id):
    f = Files.query.filter_by(id=file_id).first_or_404()

    uploader = get_uploader()
    uploader.delete(filename=f.location)

    db.session.delete(f)
    db.session.commit()
    return True


def rmdir(directory):
    shutil.rmtree(directory, ignore_errors=True)
