
import os

from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import (
    RunnablePassthrough,
    RunnableLambda
)

from langchain_openai import ChatOpenAI

from core.vector_store import (
    build_vector_store,
    load_vector_store,
    get_retriver
)

load_dotenv()


def get__llm():
    """Initialize and return the language model."""

    return ChatOpenAI(
        model="openrouter/free",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.3
    )


def format_doc(docs):
    """Convert retrieved documents into context text."""

    return "\n\n".join(
        doc.page_content for doc in docs
    )


def get_prompt():

    """Create the RAG prompt."""

    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert meeting assistant.

                Answer the user's question based ONLY on
                the meeting transcript context provided below.

                If the answer is not found in the context, say:
                "I could not find this information in the meeting transcript."

                Always be concise and precise.
                If quoting someone, mention it clearly.

                Context from meeting transcript:
                {context}
                """
            ),
            ("human", "{question}")
        ]
    )


def create_rag_chain(retriever):

    """Create the common RAG chain."""

    llm = get__llm()

    prompt = get_prompt()

    rag_chain = (
        {
            "context": retriever | RunnableLambda(format_doc),
            "question": RunnablePassthrough()
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain


def build_rag_chain(transcript: str):

    """Build vector store and RAG chain from transcript."""

    vector_store = build_vector_store(transcript)

    retriever = get_retriver(vector_store, k=4)

    return create_rag_chain(retriever)


def load_rag_chain():

    """Load an existing vector store and create RAG chain."""

    vector_store = load_vector_store()

    retriever = get_retriver(vector_store, k=4)

    return create_rag_chain(retriever)


def ask_question(rag_chain, question: str):

    """Ask a question using the RAG chain."""

    print(f"Asking question: {question}")

    answer = rag_chain.invoke(question)

    print(f"Answer: {answer}")

    return answer
