workspace "Name" "Description" {

    !identifiers hierarchical

    model {
        u = person "User"
        admin = person "Admin"

        ss = softwareSystem "Römer RAG" {
            curl = container "cURL"
            entry = container "RAG-API" {
                technology "REST API"
                description "The entry point for the user to interact with the system, Port 5600."
            }
            ollama = container "Ollama" {
                technology "Ollama, Port 11434"
                description "The Ollama service that provides the language model."
            }
            db = container "pgvector"  {
                tags "Database"
                technology "PostgreSQL with pgvector, Port 5432"
            }
            db_api = container "Vector-API" {
                technology "REST API, Port 5500"
            }

            ingest = container "Ingester" {
                technology "Python Script"
                description "A script that ingests data into the system."
            }

            curl -> entry "Sends Question"
            entry -> ollama "Generate Vector via Embedding Model"
            entry -> db_api "Sends Vector and Filter for retrieval"
            db_api -> db "Retrieves matches"
            entry -> ollama "Generates Answer from matches via LLM"

            ingest -> ingest "Create chunks from file"
            ingest -> ollama "Get Embedding for chunk"
            ingest -> db_api "Store Embedding and Chunk"
        }

        u -> ss.curl "Uses"
        admin -> ss.ingest "Ingests Data"
    }

    views {
        systemContext ss "Diagram1" {
            include *
        }

        container ss "Diagram2" {
            include *
        }

        styles {
            element "Element" {
                color #ffffff
            }
            element "Person" {
                background #05527d
                shape person
            }
            element "Software System" {
                background #066296
            }
            element "Container" {
                background #0773af
            }
            element "Database" {
                shape cylinder
            }
        }
    }

    configuration {
        scope softwaresystem
    }

}