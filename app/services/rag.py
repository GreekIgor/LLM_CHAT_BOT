from dataclasses import dataclass
from pathlib import Path

from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer

from app.config import Settings


@dataclass(frozen=True)
class SearchHit:
    source: str
    text: str
    score: float

# Класс и функции для работы с базой знаний и векторным поиском
class KnowledgeBase:
    dimension = 384

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: MilvusClient | None = None
        self._embedding_model: SentenceTransformer | None = None

    def ensure_ready(self) -> None:
        client = self._get_client()
        if not client.has_collection(collection_name=self.settings.milvus_collection):
            client.create_collection(
                collection_name=self.settings.milvus_collection,
                dimension=self.dimension,
                metric_type="COSINE",
                auto_id=True,
                enable_dynamic_field=True,
            )

    def search(self, question: str, limit: int = 4) -> list[SearchHit]:
        self.ensure_ready()
        vector = self._embed([f"query: {question}"])[0]
        results = self._get_client().search(
            collection_name=self.settings.milvus_collection,
            data=[vector],
            limit=limit,
            output_fields=["source", "text"],
            search_params={"metric_type": "COSINE"},
        )
        hits: list[SearchHit] = []
        for result in results[0]:
            entity = result.get("entity", {})
            score = float(result.get("distance", 0))
            if score >= 0.45 and entity.get("text"):
                hits.append(SearchHit(str(entity.get("source", "Документ")), str(entity["text"]), score))
        return hits

    def ingest_text(self, source: str, text: str) -> int:
        chunks = list(self._chunks(text))
        if not chunks:
            return 0
        self.ensure_ready()
        vectors = self._embed([f"passage: {chunk}" for chunk in chunks])
        rows = [
            {"vector": vector, "source": source, "text": chunk, "chunk_index": index}
            for index, (vector, chunk) in enumerate(zip(vectors, chunks, strict=True))
        ]
        self._get_client().insert(collection_name=self.settings.milvus_collection, data=rows)
        return len(rows)

    def ingest_file(self, file_path: Path, original_name: str) -> int:
        if file_path.suffix.lower() == ".pdf":
            from pypdf import PdfReader

            text = "\n".join(page.extract_text() or "" for page in PdfReader(file_path).pages)
        else:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        return self.ingest_text(original_name, text)

    def _get_client(self) -> MilvusClient:
        if self._client is None:
            self._client = MilvusClient(uri=self.settings.milvus_uri)
        return self._client

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer("intfloat/multilingual-e5-small")
        return self._embedding_model.encode(texts, normalize_embeddings=True).tolist()

    @staticmethod
    def _chunks(text: str, max_characters: int = 1100) -> list[str]:
        normalized = " ".join(text.split())
        return [normalized[index : index + max_characters] for index in range(0, len(normalized), max_characters)]
