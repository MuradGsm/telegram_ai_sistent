from fastembed import TextEmbedding

_embbeding_model: TextEmbedding | None = None

def get_embedding_model() -> TextEmbedding:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return [vector.tolist() for vector in model.embed(texts)]