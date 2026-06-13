from sentence_transformers import SentenceTransformer
from langdetect import detect

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

SUPPORTED_LANGUAGES = {
    'hi': 'Hindi',
    'kn': 'Kannada',
    'ta': 'Tamil',
    'te': 'Telugu',
    'en': 'English'
}

def detect_language(text):
    try:
        lang_code = detect(text[:500])
        return lang_code, SUPPORTED_LANGUAGES.get(lang_code, 'English')
    except:
        return 'en', 'English'

def get_embedding(text):
    return model.encode(text)

def get_embeddings_batch(texts):
    return model.encode(texts)