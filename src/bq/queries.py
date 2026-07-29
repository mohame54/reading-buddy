VEC_SEARCH_CREATE_QUERY = """
CREATE OR REPLACE VECTOR INDEX {index_name}
ON {dataset_table_id} ({embd_name})
OPTIONS(index_type = 'IVF',
  distance_type = 'COSINE',
  ivf_options = '{"num_lists": {num_lists}}');
"""


VEC_SEARCH_QUERY = """
SELECT {select_data}, distance 
FROM VECTOR_SEARCH(
  TABLE {dataset_table_id}, 
  '{embd_name}',
  (SELECT @embedding as {embd_name}),
  top_k => {topk},
  distance_type => 'COSINE');
"""


VEC_SEARCH_QUERY_CONDITIONED = """
SELECT {select_data}, distance 
FROM VECTOR_SEARCH(
  (SELECT * FROM {dataset_table_id} WHERE {condition}), 
  '{embd_name}',
  (SELECT @embedding as {embd_name}),
  top_k => {topk},
  distance_type => 'COSINE');
"""


VEC_SEARCH_QUERY_IMG = """
WITH embedding_table AS (
    SELECT {image_embd} AS embedding
)
SELECT base,distance
FROM VECTOR_SEARCH(
    TABLE {table_id},
    'image_embd',
    (SELECT @embedding FROM embedding_table),
    top_k => {top},
    distance_type => "COSINE"
)
"""


QUERY_ALL_COND="""
SELECT {select_attrs} FROM {table_query_path}
WHERE {cond};
"""


QUERY_ALL="""
SELECT {select_attrs} FROM {table_query_path};
"""


# TEXT ##############################################################
TXT_UPDATE_QUERY = """
UPDATE {dataset_table_id}
SET 
    Text = @Text,
    Embedding = @Embedding
    
WHERE 
    ID = @ID AND Index = @Index AND Media= @Media;
"""


TXT_DELETE_QUERY = """
DELETE FROM {dataset_table_id}
WHERE  ID = @ID AND Index = @Index AND Media= @Media;
"""


# IMAGE ############################################################

IMG_DELETE_QUERY = """
DELETE FROM {dataset_table_id}
WHERE id = @id;
"""



IMG_UPDATE_QUERY = """
UPDATE {dataset_table_id}
SET 
    lastTimeUpdated = @lastTimeUpdated,
    image_embd = @image_embd,
    description = @desc
    
WHERE 
    id = @id;
"""


DOCS_SELECT_ALL = """
SELECT id, title, ext, pages_number, gcs_uri, preview_gcs_uri
FROM {dataset_table_id}
ORDER BY title
LIMIT {limit}
OFFSET {offset};
"""

DOCS_COUNT = """
SELECT COUNT(*) AS total
FROM {dataset_table_id};
"""

DOC_SELECT_BY_ID = """
SELECT id, title, ext, pages_number, gcs_uri, preview_gcs_uri
FROM {dataset_table_id}
WHERE id = @id;
"""

PAGES_SELECT_BY_DOC = """
SELECT id, doc_id, page_number, content, audio_gcs_uri, content_aligned
FROM {dataset_table_id}
WHERE doc_id = @doc_id
ORDER BY page_number;
"""

PAGES_SELECT_FIRST = """
SELECT doc_id, content
FROM {dataset_table_id}
WHERE doc_id = @doc_id AND page_number = 1
LIMIT 1;
"""

PAGE_SELECT = """
SELECT id, doc_id, page_number, content, audio_gcs_uri, content_aligned
FROM {dataset_table_id}
WHERE doc_id = @doc_id AND page_number = @page_number
LIMIT 1;
"""

DOC_DELETE_BY_ID = """
DELETE FROM {dataset_table_id}
WHERE id = @id;
"""

PAGES_DELETE_BY_DOC = """
DELETE FROM {dataset_table_id}
WHERE doc_id = @doc_id;
"""
