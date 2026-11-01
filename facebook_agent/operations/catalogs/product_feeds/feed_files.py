"""Shared helpers for product feed uploads (not an operation itself)."""
import os
import tempfile

from facebook_agent.config import UPLOAD_TIMEOUT
from facebook_agent.graph import call_graph

FEED_EXTENSIONS = (".csv", ".tsv", ".xml", ".xlsx", ".json")  # formats acceptés par les deux opérations
FORMAT_ERROR = "Format de fichier invalide."
FORMAT_HELP = "Le fichier doit être au format CSV, TSV, XML, XLSX ou JSON (.csv, .tsv, .xml, .xlsx, .json)."

MIME_TYPES = {
    ".csv": "text/csv",
    ".tsv": "text/plain",
    ".xml": "application/xml",
    ".json": "application/json",
}


def prepare_local_feed(file_path: str) -> tuple[str, str]:
    """Return the file to upload and its MIME type for a local feed file.

    An ``.xlsx`` file is converted to a temporary CSV file first.

    Args:
        file_path: Path of the local feed file.

    Returns:
        (path_to_upload, mime_type); the path differs from file_path for an .xlsx file.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".xlsx":
        import pandas as pd  # import tardif (environ 1,7 s) : seulement pour convertir un .xlsx
        df = pd.read_excel(file_path)
        temp_csv = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp_csv.close()
        df.to_csv(temp_csv.name, index=False)
        file_path, ext = temp_csv.name, ".csv"
    return file_path, MIME_TYPES.get(ext, "text/csv")


def upload_local_feed(file_path: str, upload_path: str, access_token: str, error_message: str) -> dict:
    """Upload a local feed file. The temporary CSV created from an .xlsx is always deleted.

    Args:
        file_path: Path of the local feed file.
        upload_path: Graph API path of the upload (e.g. "FEED_ID/uploads").
        access_token: User access token.
        error_message: Message of the error result.

    Returns:
        A standard result (see call_graph).
    """
    local_path, file_type = prepare_local_feed(file_path)
    try:
        with open(local_path, "rb") as feed_file:
            return call_graph(
                "POST", upload_path, access_token,
                files={"file": (os.path.basename(local_path), feed_file, file_type)},
                error_message=error_message,
                timeout=UPLOAD_TIMEOUT,
            )
    finally:
        if local_path != file_path:
            os.remove(local_path)
