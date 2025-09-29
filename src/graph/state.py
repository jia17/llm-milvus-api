from typing import List, Dict, Any, Optional, TypedDict, Annotated
from dataclasses import dataclass
from enum import Enum

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

from src.vector_store.milvus_store import SearchHit


class TaskType(Enum):
    DOCUMENT_UPLOAD = "document_upload"
    QUERY = "query" 
    CHAT = "chat"


class IntentType(Enum):
    KNOWLEDGE_QUERY = "knowledge_query"
    CASUAL_CHAT = "casual_chat" 
    DOCUMENT_UPLOAD = "document_upload"
    UNCERTAIN = "uncertain"


@dataclass
class DocumentInfo:
    file_path: str
    filename: str
    content: str
    doc_id: str


class GraphState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    query: str
    task_type: TaskType
    intent_type: Optional[IntentType]
    intent_confidence: float
    
    # Document processing
    uploaded_file: Optional[str]
    document: Optional[DocumentInfo]
    processing_error: Optional[str]
    
    # Retrieval
    retrieval_results: List[SearchHit]
    dense_results: List[SearchHit]
    sparse_results: List[SearchHit]
    retrieval_time: float
    
    # Generation
    answer: str
    sources: List[SearchHit]
    generation_time: float
    
    # Metadata
    total_time: float
    error: Optional[str]
    metadata: Dict[str, Any]