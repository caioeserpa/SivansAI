import json
import os
import sys
import time
import types
import warnings
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Compatibilidade: langchain-community >= 0.4 removeu o módulo legado vertexai,
# mas o ragas 0.4.x ainda tenta importá-lo no arquivo ragas.llms.base.
if "langchain_community.chat_models.vertexai" not in sys.modules:
    dummy_vertex = types.ModuleType("langchain_community.chat_models.vertexai")
    class ChatVertexAI: pass
    dummy_vertex.ChatVertexAI = ChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = dummy_vertex

try:
    from langchain_community.llms import VertexAI
except ImportError:
    try:
        import langchain_community.llms
        class VertexAI: pass
        langchain_community.llms.VertexAI = VertexAI
    except Exception:
        pass

import mlflow
import requests
from datasets import Dataset
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from ragas import evaluate
from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy, context_precision, faithfulness
from ragas.run_config import RunConfig

BASE_API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/").replace("localhost", "127.0.0.1")
API_URL = f"{BASE_API_URL}/chat" if not BASE_API_URL.endswith("/chat") else BASE_API_URL
GOLD_FILE = Path(__file__).parent / "gold_questions.json"
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
MLFLOW_EXPERIMENT = "vale-amanhecer-rag"

# Marcador usado no template para identificar a entrada de exemplo (não deve ser avaliada).
MARCADOR_EXEMPLO = "(EXEMPLO"


def load_gold_questions():
    with open(GOLD_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    perguntas_validas = [
        item for item in data
        if item.get("pergunta", "").strip() and MARCADOR_EXEMPLO not in item["pergunta"]
    ]

    if not perguntas_validas:
        raise ValueError(
            "Nenhuma pergunta válida encontrada em gold_questions.json. "
            "Preencha pelo menos algumas perguntas reais (apagando ou ignorando a linha de exemplo) antes de rodar a avaliação."
        )

    return perguntas_validas


def call_chat_api(pergunta: str):
    last_exc = None
    for tentativa in range(1, 4):
        try:
            response = requests.post(API_URL, json={"pergunta": pergunta}, timeout=300)
            if not response.ok:
                print(f"[evaluate_ragas] Resposta de erro da API ({response.status_code}): {response.text}")
            response.raise_for_status()
            data = response.json()
            return data["resposta"], data.get("contextos", [])
        except Exception as exc:
            last_exc = exc
            print(f"[evaluate_ragas] Tentativa {tentativa}/3 falhou: {exc}")
            if tentativa < 3:
                time.sleep(5)
    raise last_exc


def build_dataset(gold_questions: list):
    samples = []
    for item in gold_questions:
        pergunta = item["pergunta"]
        resposta_esperada = item.get("resposta_esperada", "")

        print(f"[evaluate_ragas] Perguntando: {pergunta}")
        resposta_gerada, contextos = call_chat_api(pergunta)

        samples.append(
            SingleTurnSample(
                user_input=pergunta,
                response=resposta_gerada,
                retrieved_contexts=contextos if contextos else [""],
                reference=resposta_esperada,
            )
        )

    return EvaluationDataset(samples=samples)


def get_local_judge():
    """Usa o LLM local (via Ollama) e o embedding local como 'juízes' do RAGAS,
    para não precisar de chave da OpenAI."""
    llm_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip()
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().replace("localhost", "127.0.0.1")
    embedding_model_name = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small").strip()

    chat_model = ChatOllama(
        model=llm_model,
        base_url=ollama_base_url,
        temperature=0.0,
        num_predict=512,
        num_ctx=4096,
        repeat_penalty=1.15,
    )
    embedding_model = HuggingFaceEmbeddings(model_name=embedding_model_name)

    return LangchainLLMWrapper(chat_model), LangchainEmbeddingsWrapper(embedding_model)


def main():
    gold_questions = load_gold_questions()
    print(f"[evaluate_ragas] {len(gold_questions)} pergunta(s) válida(s) no gabarito.")

    dataset = build_dataset(gold_questions)
    judge_llm, judge_embeddings = get_local_judge()

    print("\n[evaluate_ragas] Calculando métricas RAGAS (pode demorar — o LLM local roda várias vezes por pergunta)...")
    run_config = RunConfig(timeout=360, max_workers=1, max_retries=3)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
        llm=judge_llm,
        embeddings=judge_embeddings,
        run_config=run_config,
    )

    df = result.to_pandas()

    # Salva o resultado bruto imediatamente
    resultado_csv = Path(__file__).parent / "ultimo_resultado.csv"
    df.to_csv(resultado_csv, index=False)

    # Normaliza colunas para compatibilidade com versões do RAGAS e scripts de revisão
    if "user_input" in df.columns and "question" not in df.columns:
        df["question"] = df["user_input"]
    if "response" in df.columns and "answer" not in df.columns:
        df["answer"] = df["response"]
    if "retrieved_contexts" in df.columns and "contexts" not in df.columns:
        df["contexts"] = df["retrieved_contexts"]
    if "reference" in df.columns and "ground_truth" not in df.columns:
        df["ground_truth"] = df["reference"]

    df.to_csv(resultado_csv, index=False)

    col_q = "question" if "question" in df.columns else ("user_input" if "user_input" in df.columns else df.columns[0])
    cols_para_exibir = [c for c in [col_q, "faithfulness", "answer_relevancy", "context_precision"] if c in df.columns]

    print("\n[evaluate_ragas] Resultado por pergunta:")
    print(df[cols_para_exibir].to_string(index=False))

    medias = {}
    for metrica in ["faithfulness", "answer_relevancy", "context_precision"]:
        if metrica in df.columns:
            valores = df[metrica].dropna()
            medias[f"{metrica}_medio"] = round(float(valores.mean()), 4) if not valores.empty else 0.0

    print(f"\n[evaluate_ragas] Médias: {medias}")

    try:
        db_path = Path(__file__).resolve().parent.parent / "mlflow.db"
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", f"sqlite:///{db_path}")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(MLFLOW_EXPERIMENT)

        with mlflow.start_run():
            mlflow.log_param("modelo_llm", os.getenv("OLLAMA_MODEL", "llama3.2:3b"))
            mlflow.log_param("modelo_embedding", os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small"))
            mlflow.log_param("modelo_reranker", os.getenv("RERANKER_MODEL", "unicamp-dl/mMiniLM-L6-v2-pt-v2"))
            mlflow.log_param("total_perguntas", len(gold_questions))

            for nome, valor in medias.items():
                mlflow.log_metric(nome, valor)

            mlflow.log_artifact(str(resultado_csv))

        print("\n[evaluate_ragas] Resultados registrados no MLflow.")
        print(f"[evaluate_ragas] Rode 'mlflow ui --backend-store-uri {tracking_uri}' e acesse http://localhost:5000 para ver.")
    except Exception as exc:
        print(f"\n[evaluate_ragas] Aviso: Não foi possível gravar no MLflow ({exc}).")
        print(f"[evaluate_ragas] Os resultados continuam salvos com segurança em {resultado_csv}.")


if __name__ == "__main__":
    main()
