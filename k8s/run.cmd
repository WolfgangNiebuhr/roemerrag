start "" kubectl port-forward -n experimental services/ollama 11434:11434
start "" kubectl port-forward -n experimental services/vector-api 5500:5500
start "" kubectl port-forward -n experimental services/rag-api 5600:5600
