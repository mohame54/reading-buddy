import os
import math
import time
import json
import base64
import logging
from google.cloud import storage
from google.cloud import bigquery
from google.oauth2 import service_account
from typing import List, Optional, Union, Sequence, Literal


logger = logging.getLogger(__name__)
TASK_TYPE = Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"]

_bq_client = None

def get_gemini_embeds(
    model,
    contents: Union[Sequence[str], str],
    dim:Optional[int]=None,
    chunk_size :Optional[int] = 1000,
    max_toks_request_size: Optional[int] = 20000,
    batch_size: Optional[int] = None,
    poll_time:Optional[int] = 0,
    task: Optional[TASK_TYPE] = "RETRIEVAL_DOCUMENT"
) -> Union[List[List[float]], List[float]]:
    start_time = time.time()
    is_single_string = isinstance(contents, str)
    num_contents = 1 if is_single_string else len(contents)
    
    logger.info(f"🔢 Generating embeddings for {num_contents} item(s), task={task}, dim={dim}")

    from vertexai.language_models import TextEmbeddingInput

    def get_embd(texts):
        inputs = [TextEmbeddingInput(text, task) for text in texts]
        kwargs = dict(output_dimensionality=dim) if dim else {}
        embeddings = model.get_embeddings(inputs, **kwargs)
        return [embedding.values for embedding in embeddings]
    
    if is_single_string:
       contents = [contents]
       result = get_embd(contents)[0]
       elapsed = time.time() - start_time
       logger.info(f"✅ Generated single embedding in {elapsed:.3f}s")
       return result
    
    out = []
    opt_batch_size = math.floor(max_toks_request_size / chunk_size)
    batch_size = float("inf") if batch_size is None else batch_size
    batch_size = min(opt_batch_size, batch_size)
    
    num_batches = math.ceil(len(contents) / batch_size)
    logger.info(f"📦 Processing {num_batches} batch(es) with batch_size={batch_size}")
    
    for batch_idx, i in enumerate(range(0, len(contents), batch_size), 1):
        batch_start = time.time()
        sub = contents[i : i + batch_size]
        out.extend(get_embd(sub))
        batch_elapsed = time.time() - batch_start
        logger.info(f"   Batch {batch_idx}/{num_batches}: {len(sub)} items in {batch_elapsed:.3f}s")
        if poll_time > 0:
           time.sleep(poll_time)
    
    total_elapsed = time.time() - start_time
    logger.info(f"✅ Generated {len(out)} embeddings in {total_elapsed:.3f}s (avg: {total_elapsed/len(out):.3f}s per item)")
    return out


def setup_bq_creds(bq_cred_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = bq_cred_path


def load_json(json_obj:str, from_str=False):
    if from_str:
        return json.loads(json_obj)
    with open(json_obj, "rb") as f:
      data = json.load(f)
    return data 


def get_creds(
    credentials_info: Union[dict, str],
    from_b64: Optional[bool]=False
):
    if from_b64:
        credentials_info = base64_2bytes(credentials_info)
    if isinstance(credentials_info, (bytes, str)):
        credentials_info = load_json(credentials_info, from_str=True)
    SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info, scopes=SCOPES)
    return credentials

def get_bq_client(
    credentials_info: Union[dict, str],
    proj_id: str,
    from_b64: Optional[bool]=False,
):
    creds = get_creds(credentials_info, from_b64=from_b64)
    client = bigquery.Client(project=proj_id, credentials=creds)
    return client

def load_bq_client(
    credentials_info: Union[dict, str],
    proj_id: str,
    from_b64: Optional[bool]=False,
    force_new: Optional[bool]=False
):
    if force_new:
        logger.debug(f"🔨 Creating new BigQuery client for project '{proj_id}' (force_new=True)")
        return get_bq_client(credentials_info, proj_id, from_b64=from_b64)
    
    global _bq_client
    if _bq_client is None:
        logger.info(f"🌐 Creating shared BigQuery client for project '{proj_id}'")
        _bq_client = get_bq_client(credentials_info, proj_id, from_b64=from_b64)
    else:
        logger.debug(f"♻️  Reusing shared BigQuery client for project '{proj_id}'")
    return _bq_client


def load_gcp_bucket_client(
    credentials_info: Union[dict, str],
    proj_id: Optional[str]= None,
    from_b64: Optional[bool]=False
):
    creds = get_creds(credentials_info, from_b64=from_b64)
    client = storage.Client(project=proj_id,credentials=creds)
    return client


def setup_vertex_ai(creds_info: Union[dict, str], proj_id: str, from_b64: Optional[bool]=False):
    import vertexai

    creds = get_creds(creds_info, from_b64=from_b64)
    vertexai.init(credentials=creds, project=proj_id)


def get_client_bucket(
    client,
    bucket_name,
    **bucket_kwargs
):
    found = False
    for bucket in client.list_buckets():
        if bucket.name == bucket_name:
            bucket_client = client.bucket(bucket_name)
            found = True
            break
    if not found:
       print(f"[Info]: Creating a Bucket: {bucket_name} !")
       bucket_client = client.bucket(bucket_name)
       bucket_client = client.create_bucket(bucket_client, **bucket_kwargs)
    return bucket_client


def base64_2bytes(base64_str:str):
    return base64.b64decode(base64_str.encode("utf-8"))


def bytes_2base64(byts):
    return base64.b64encode(byts).decode("utf-8")


def load_content(pth):
    return bytes_2base64(open(pth, "rb").read())