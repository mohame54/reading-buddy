import gdown
import os



def download_model():
    FOLDER_DRIVE_ID = os.getenv('FOLDER_DRIVE_ID')

    if not FOLDER_DRIVE_ID:
        raise ValueError("FOLDER_DRIVE_ID is not set")

    gdown.download_folder(id=FOLDER_DRIVE_ID, output='models')


if __name__ == "__main__":
    download_model()