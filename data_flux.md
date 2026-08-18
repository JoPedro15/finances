```mermaid
flowchart TD
    subgraph INFRA["1. INFRAESTRUTURA & ARMAZENAMENTO"]
        GDRIVE["Google Drive API<br/>(Backup Remoto)"]
        LOCAL_DATA["Base de Dados & Ficheiros<br/>• finances.db (SQLite)<br/>• portfolio.json<br/>• portfolio_targets.json"]
    end

    subgraph INGESTION["2. INGESTÃO DE DADOS DE MERCADO"]
        YF["yfinance API"]
        JE["JustETF Client"]
        CACHE["etf_cache.json<br/>(Cache Local)"]
        
        GQ["get_asset_quotation"]
        SP["StockProvider"]
        EP["ETFProvider"]
    end

    subgraph ENGINE["3. CAMADA CORE & PROCESSAMENTO"]
        PDE["PortfolioDecisionEngine<br/>(Stock & ETF Scoring Strategies)"]
        ANL["Snapshot & Analysis Core"]
    end

    subgraph CLI["4. CAMADA DE INTERFACE (MAKEFILE)"]
        C_SYNC["Sincronização & Migração<br/>• make push-config / pull-config<br/>• make sync-portfolio / migrate"]
        C_INSPECT["Analítica & Inspeção (Read-Only)<br/>• make get-snapshot / save-snapshot / analyze<br/>• make etf-details / stock-details / analyze-exposure"]
        C_DECIDE["Decisão & Alocação (Actionable)<br/>• make rebalance<br/>• make recommend"]
    end

    %% Conexões
    GDRIVE <--> LOCAL_DATA
    JE <--> CACHE

    YF --> GQ & SP
    JE --> EP

    LOCAL_DATA & GQ & SP & EP --> PDE
    LOCAL_DATA & GQ & SP & EP --> ANL

    PDE --> C_DECIDE
    ANL --> C_INSPECT
    LOCAL_DATA --> C_SYNC