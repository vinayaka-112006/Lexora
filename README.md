# Lexora – AI-Powered Legal & Regulatory Intelligence for the Ayurveda Sector

**Making complex legal and regulatory information more accessible through Retrieval-Augmented Generation (RAG).**

Lexora is an AI-powered legal information platform designed to help Ayurveda entrepreneurs, researchers, startups, and traditional practitioners explore legal and regulatory information related to intellectual property rights, traditional knowledge protection, biodiversity regulations, product regulations, and international compliance.

The platform uses a Retrieval-Augmented Generation (RAG) pipeline to retrieve relevant information from a curated collection of Indian and international legal documents and generate context-aware responses supported by source references.

---

## Problem Statement

The Ayurveda industry is continuously evolving, creating opportunities for innovation, research, and commercialization. However, navigating the legal and regulatory landscape can be challenging.

Entrepreneurs and researchers often need to refer to multiple legal documents, regulations, and international frameworks to understand topics such as:

- Intellectual property rights and patentability.
- Protection of traditional knowledge.
- Biodiversity regulations and access to biological resources.
- Regulatory requirements for Ayurveda-related products.
- International intellectual property and regulatory frameworks.

Since this information is distributed across numerous documents and legal sources, identifying relevant provisions and understanding them can be time-consuming.

**Lexora aims to simplify this process by providing a centralized, conversational interface for exploring curated legal and regulatory information.**

## Key Features

### 1. AI-Powered Legal Information Assistant
- Ask legal and regulatory questions using natural language.
- Retrieve relevant information from curated legal documents.
- Generate context-aware responses using an LLM.
- Display supporting references for retrieved information.

### 2. Hybrid Retrieval System
Combines semantic search and keyword-based search to improve document retrieval.

- **Dense Retrieval:** Uses sentence embeddings to identify semantically relevant content.
- **BM25 Retrieval:** Finds relevant documents through keyword matching.
- **Reciprocal Rank Fusion (RRF):** Combines results from both retrieval methods to produce a unified ranking.

### 3. Source Validation and Response Assessment
- Citation validation to check whether generated references correspond to retrieved sources.
- Claim verification to identify supported, uncertain, and unsupported claims.
- Confidence assessment to help evaluate the reliability of generated responses.
- Abstention mechanism for questions that cannot be adequately answered from the available knowledge base.

### 4. Jurisdiction-Based Retrieval
Supports filtering legal information based on:
- Indian legal and regulatory documents.
- International legal and regulatory documents.
- Combined retrieval across available jurisdictions.

### 5. Legal and Regulatory News
A separate news feature retrieves recent developments related to Ayurveda, intellectual property, and regulatory affairs using the Tavily API.

### 6. User Authentication and Chat History
- User registration and login.
- Authenticated access to the platform.
- Conversation history management.
- Interactive chat interface.

---

## System Architecture

```text
             USER
               |
               v
       REACT FRONTEND
               |
               v
       NODE.JS / EXPRESS
               |
       +-------+--------+
       |                |
       v                v
  MongoDB          FASTAPI RAG SERVICE
  - Users                |
  - Chat History         v
                   QUERY PROCESSING
                         |
                         v
                  HYBRID RETRIEVAL
                    /         \
                   v           v
              Dense Search   BM25 Search
                   \           /
                    v         v
                  RECIPROCAL RANK
                    FUSION (RRF)
                         |
                         v
                   TOP-K CONTEXT
                         |
                         v
                    OLLAMA LLM
                         |
                         v
                RESPONSE VALIDATION
                - Citation Validation
                - Claim Verification
                - Confidence Assessment
                - Abstention Handling
                         |
                         v
                  FINAL RESPONSE
                         |
                         v
                   USER INTERFACE


       LEGAL DOCUMENT KNOWLEDGE BASE
                    |
                    v
              PDF EXTRACTION
                    |
                    v
                CHUNKING
                    |
                    v
             TEXT EMBEDDINGS
                    |
                    v
                 CHROMADB
                    |
                    v
             HYBRID RETRIEVAL
```

---

## RAG Pipeline

Lexora follows a Retrieval-Augmented Generation workflow.

1. **Document Collection:** Curated Indian and international legal documents are collected in PDF format.
2. **Text Extraction:** Text is extracted from PDF documents, with OCR used where required for scanned content.
3. **Text Chunking:** Extracted content is divided into smaller chunks for efficient retrieval.
4. **Embedding Generation:** Sentence Transformers converts text chunks into vector embeddings.
5. **Vector Storage:** Embeddings and associated metadata are stored in ChromaDB.
6. **Query Processing:** User questions are converted into embeddings and processed for retrieval.
7. **Hybrid Retrieval:** Dense semantic retrieval and BM25 keyword retrieval identify relevant chunks.
8. **Rank Fusion:** Reciprocal Rank Fusion combines the retrieval results.
9. **Response Generation:** Retrieved context is passed to the local LLM through Ollama.
10. **Response Validation:** Citation validation, claim verification, confidence assessment, and abstention mechanisms are applied before presenting the response.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React.js, Vite, JavaScript, CSS |
| Backend | Node.js, Express.js |
| RAG Service | Python, FastAPI |
| Database | MongoDB |
| Vector Database | ChromaDB |
| Embedding Model | Sentence Transformers – `all-MiniLM-L6-v2` |
| Language Model | Llama 3 through Ollama |
| Retrieval | Dense Search, BM25, Reciprocal Rank Fusion |
| News Integration | Tavily API |
| Document Processing | PDF extraction, OCR, text chunking |
| Version Control | Git, GitHub |

---

## Project Structure

```text
mini_project/
│
├── frontend/
│   └── React + Vite application
│
├── backend/
│   └── Node.js + Express application
│
├── rag-service/
│   ├── app/
│   │   └── RAG application modules
│   │
│   ├── corpus/
│   │   ├── national/
│   │   └── international/
│   │
│   ├── chroma_db/
│   │   └── Vector database (generated locally)
│   │
│   └── requirements.txt
│
├── .gitignore
└── README.md
```

*Note: This is a high-level representation. Refer to the individual directories for the complete implementation structure.*

---

## Getting Started

### Prerequisites

Make sure the following tools are installed:

- Node.js and npm
- Python 3.11
- MongoDB
- Ollama
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/vinayaka-112006/Lexora.git
cd Lexora
```

### 2. Set Up the Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Set Up the Node.js Backend

Open another terminal:

```bash
cd backend
npm install
```

Configure the required environment variables in your `.env` file and start the backend using the appropriate script defined in `package.json`.

For example:

```bash
npm run dev
```

### 4. Set Up the Python RAG Service

Open another terminal:

```bash
cd rag-service

python -m venv .venv
```

Activate the environment:

**Windows PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure the required environment variables and start the FastAPI service using the actual application entry point.

For example, if the FastAPI instance is `app.main:app`:

```bash
uvicorn app.main:app --reload
```

### 5. Configure Ollama

Install Ollama and download the required model:

```bash
ollama pull llama3
```

Start the Ollama service:

```bash
ollama serve
```

Make sure the RAG service is configured to connect to your local Ollama instance.

### 6. Configure Environment Variables

Create the required `.env` files in the respective application directories.

Typical configuration may include:

```env
# Backend
PORT=
MONGODB_URI=
JWT_SECRET=
TAVILY_API_KEY=

# RAG Service
OLLAMA_MODEL=
OLLAMA_BASE_URL=
CHROMA_DB_PATH=
```


---

## Current Implementation Highlights

| Component | Details |
|---|---|
| Legal PDF collection | 19 curated documents |
| Total document pages | Approximately 660 |
| Generated chunks | 1,349 |
| Indian document chunks | 976 |
| International document chunks | 373 |
| Embedding model | all-MiniLM-L6-v2 |
| Vector database | ChromaDB |
| Retrieval approach | Dense + BM25 + RRF |
| Final retrieved context | Top 5 chunks |
| LLM | Llama 3 via Ollama |

---

## Future Enhancements

- **Multilingual Support:** Enable legal information queries in regional languages such as Kannada, Hindi, and Tamil.
- **Automated Legal Updates:** Monitor official legal portals and identify amendments and regulatory notifications.
- **Advanced Retrieval:** Introduce reranking, query rewriting, and improved contextual retrieval.
- **Document Analysis:** Allow users to upload legal documents, patents, agreements, and research papers for analysis.
- **Compliance Assistance:** Generate structured regulatory checklists based on product categories and business requirements.
- **Legal Knowledge Graph:** Establish relationships between legal provisions, regulatory authorities, products, and intellectual property concepts.

---


