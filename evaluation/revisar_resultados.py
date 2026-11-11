from pathlib import Path
 
import pandas as pd
 
CSV_PATH = Path(__file__).parent / "ultimo_resultado.csv"
TOP_N = 5
 
 
def main():
    if not CSV_PATH.exists():
        print(f"[revisar_resultados] Não encontrei {CSV_PATH}.")
        print("[revisar_resultados] Rode 'python evaluation/evaluate_ragas.py' primeiro.")
        return
 
    df = pd.read_csv(CSV_PATH)
 
    if "context_precision" not in df.columns:
        print("[revisar_resultados] O arquivo CSV não tem a coluna 'context_precision'. Rode evaluate_ragas.py de novo.")
        return
 
    piores = df.sort_values("context_precision").head(TOP_N)
 
    print(f"[revisar_resultados] As {len(piores)} pergunta(s) com pior Context Precision:\n")
    for _, row in piores.iterrows():
        print("=" * 70)
        print(f"Pergunta: {row['question']}")
        print(f"Context Precision: {row['context_precision']:.3f}")
        resposta_resumida = str(row["answer"])[:200]
        print(f"Resposta gerada: {resposta_resumida}...")
        print()
 
    print("-" * 70)
    print("Dica: se alguma dessas perguntas usa um termo específico da doutrina que não")
    print("apareceu certo na busca, adicione esse termo (e suas variações/sinônimos)")
    print("em data_pipeline/glossario.json e chame POST /recarregar-glossario — sem")
    print("precisar reiniciar a API nem reindexar nada no Qdrant.")
 
 
if __name__ == "__main__":
    main()
 