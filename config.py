SKYSTONES_PER_REFRESH = 3
BOOKMARK_GOLD  = 184_000
MYSTIC_GOLD    = 280_000
FRIENDSHIP_GOLD = 18_000
BOOKMARK_AMOUNT = 5
MYSTIC_AMOUNT   = 50
FRIENDSHIP_AMOUNT = 50

MYSTIC_IDX   = 0
BOOKMARK_IDX = 1
FRIENDSHIP_IDX = 2

DIALOG_ATTEMPTS = 3
DIALOG_RETRY_DELAY = 0.5
MAX_REFRESH_FAILURES = 3
ROW_TOLERANCE_PX = 50

ITENS = {
    "en": ["Mystic Medals", "Covenant Bookmarks", "Friendship Points"],
    "pt": ["Medalhas Místicas", "Marca-Páginas da Aliança", "Pontos de Amizade"],
}

SOLD_OUT_STR = "0/"

REFRESH_STR = {"en": "Refresh", "pt": "Renovar"}
CANCEL_STR  = {"en": "Cancel",  "pt": "Cancelar"}
BUY_STR     = {"en": "Buy",     "pt": "Comprar"}

LOG = {
    "pt": {
        "connecting":     "Conectando ao dispositivo...",
        "connected":      "Conectado!",
        "max_reached":    "Número máximo de renovações atingido.",
        "cycle":          "=== Ciclo {} ===",
        "scrolling":      "Scrollando para baixo...",
        "no_dialog":      "Dialog de confirmação não encontrado.",
        "confirming":     "Confirmando em ({}, {})...",
        "no_confirm_btn": "Botão de confirmação não encontrado.",
        "no_buy_ocr":     "Botão Comprar não encontrado via OCR, clicando 160px à direita...",
        "item_found":     "'{}' encontrado! Comprando...",
        "sold_out":       "'{}' já comprado nesta loja, pulando.",
        "refreshing":     "Renovando em {}...",
        "no_refresh_btn": "Botão '{}' não encontrado!",
        "no_refresh_dialog": "Dialog de renovação não encontrado, renovação não confirmada.",
        "dialog_closed":  "Janela aberta encontrada, fechando em Cancelar...",
        "debug_saved":    "Print da tela salvo em {}",
        "refresh_aborted": "Renovação falhou {} vezes seguidas, encerrando.",
        "error":          "Erro: {}",
        "targets":        "Itens selecionados: {}",
        "bot_stopped":    "Bot encerrado.",
    },
    "en": {
        "connecting":     "Connecting to device...",
        "connected":      "Connected!",
        "max_reached":    "Maximum number of refreshes reached.",
        "cycle":          "=== Cycle {} ===",
        "scrolling":      "Scrolling down...",
        "no_dialog":      "Confirmation dialog not found.",
        "confirming":     "Confirming at ({}, {})...",
        "no_confirm_btn": "Confirmation button not found.",
        "no_buy_ocr":     "Buy button not found via OCR, clicking 160px to the right...",
        "item_found":     "'{}' found! Buying...",
        "sold_out":       "'{}' already bought in this shop, skipping.",
        "refreshing":     "Refreshing at {}...",
        "no_refresh_btn": "'{}' button not found!",
        "no_refresh_dialog": "Refresh dialog not found, refresh not confirmed.",
        "dialog_closed":  "Open dialog found, closing it with Cancel...",
        "debug_saved":    "Screenshot saved to {}",
        "refresh_aborted": "Refresh failed {} times in a row, stopping.",
        "error":          "Error: {}",
        "targets":        "Selected items: {}",
        "bot_stopped":    "Bot stopped.",
    },
}

UI = {
    "pt": {
        "title":        "Secret Shop Bot",
        "lang_label":   "Idioma do jogo:",
        "mode_sky":     "Skystones",
        "mode_ref":     "Renovações",
        "sky_hint":     "renovações",
        "ref_hint":     "skystones serão gastas",
        "invalid_mult": "Skystones deve ser múltiplo de 3!",
        "invalid_val":  "Valor inválido!",
        "items_label":  "Itens para comprar",
        "no_items":     "Selecione ao menos um item!",
        "btn_start":    "Iniciar",
        "btn_stop":     "Parar",
        "lbl_start":    "Início:",
        "lbl_end":      "Fim:",
        "lbl_duration": "Duração:",
        "lbl_refreshes":"Renovações:",
        "lbl_bookmarks":"Marca-Páginas:",
        "lbl_mystics":  "Medalhas Místicas:",
        "lbl_friendship":"Pontos de Amizade:",
        "lbl_gold":     "Ouro gasto:",
        "purchases":    "compra(s)",
    },
    "en": {
        "title":        "Secret Shop Bot",
        "lang_label":   "Game language:",
        "mode_sky":     "Skystones",
        "mode_ref":     "Refreshes",
        "sky_hint":     "refreshes",
        "ref_hint":     "skystones will be spent",
        "invalid_mult": "Skystones must be a multiple of 3!",
        "invalid_val":  "Invalid value!",
        "items_label":  "Items to buy",
        "no_items":     "Select at least one item!",
        "btn_start":    "Start",
        "btn_stop":     "Stop",
        "lbl_start":    "Start:",
        "lbl_end":      "End:",
        "lbl_duration": "Duration:",
        "lbl_refreshes":"Refreshes:",
        "lbl_bookmarks":"Bookmarks:",
        "lbl_mystics":  "Mystic Medals:",
        "lbl_friendship":"Friendship Points:",
        "lbl_gold":     "Gold spent:",
        "purchases":    "purchase(s)",
    },
}
