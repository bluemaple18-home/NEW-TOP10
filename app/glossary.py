# -*- coding: utf-8 -*-
"""
股市術語與指標白話文解釋庫 (Glossary)
用於「新手教學模式」，將專業術語翻譯成白話文。
"""

GLOSSARY = {
    # ===== 基礎觀念 =====
    "均線": {
        "title": "移動平均線 (MA)",
        "simple": "大家的平均成本。",
        "detail": "MA5 (5日線) 代表最近5天大家的平均成本，MA20 (月線) 代表最近一個月。如果股價在均線之上，代表大家大多賺錢，賣壓較輕；反之則代表大家賠錢，容易有解套賣壓。"
    },
    "成交量": {
        "title": "成交量 (Volume)",
        "simple": "股票的人氣指標。",
        "detail": "代表這檔股票今天交易的熱絡程度。通常股價上漲時，最好伴隨成交量放大（價漲量增），代表是真材實料的上漲；如果只有量大但價格不漲，甚至下跌，就要小心有人在出貨。"
    },
    "K線": {
        "title": "K線 (Candlestick)",
        "simple": "紀錄一天股價變化的蠟燭圖。",
        "detail": "紅K代表今天收盤比開盤高（漲），黑/綠K代表收盤比開盤低（跌）。實體部分代表開盤與收盤的區間，上下影線代表最高與最低價走過的痕跡。"
    },
    
    # ===== 進階指標 =====
    "KD": {
        "title": "KD 指標 (隨機指標)",
        "simple": "判斷股價是「太貴」還是「太便宜」的溫度計。",
        "detail": "數值範圍 0-100。\n• 超過 80 (過熱)：股價可能漲多了，隨時可能回檔。\n• 低於 20 (超賣)：股價可能跌過頭了，隨時可能反彈。\n• 黃金交叉 (K由下往上穿過D)：短線轉強訊號。"
    },
    "MACD": {
        "title": "MACD 指標",
        "simple": "判斷中長期趨勢方向的工具。",
        "detail": "• 柱狀圖由綠轉紅：空頭轉多頭，是買進訊號。\n• 柱狀圖由紅轉綠：多頭轉空頭，是賣出訊號。\n• DIF 與 Signal 線都在 0 軸之上：代表目前是多頭趨勢（漲勢）。"
    },
    "布林通道": {
        "title": "布林通道 (Bollinger Bands)",
        "simple": "股價波動的「車道」。",
        "detail": "由上軌、中軌、下軌組成。\n• 股價通常會在上下軌之間游走。\n• 突破上軌：股價極強，但也可能即將拉回。\n• 壓縮：當通道變得很窄，代表即將出現大行情（大漲或大跌）。"
    },

    # ===== 推薦理由術語 =====
    "W底成型突破頸線": {
        "title": "W底突破",
        "simple": "打底完成，準備起飛。",
        "detail": "股價兩次跌到低點都沒破，形成像英文 'W' 的形狀，並且突破了中間的高點（頸線）。這代表賣壓已經被消化完畢，多方力量獲勝，是強力的買進訊號。"
    },
    "W底": {  # Alias
        "title": "W底 (雙重底)",
        "simple": "兩次測試低點不破，底部紮實。",
        "detail": "股價經過兩次下跌測試支撐，顯示低檔有強大買盤，不易再跌。"
    },
    "均線多頭排列": {
        "title": "均線多頭排列",
        "simple": "短期、中期、長期趨勢都向上。",
        "detail": "5日線 > 20日線 > 60日線，且全部向上。這代表短中長線的投資人都賺錢，趨勢非常強勁，容易產生波段行情。"
    },
    "MACD黃金交叉": {
        "title": "MACD 黃金交叉",
        "simple": "趨勢由跌轉漲的轉折點。",
        "detail": "MACD 的快線 (DIF) 向上穿過慢線 (Signal)，通常發生在股價整理結束，準備發動攻勢的時候。"
    },
    "爆量長紅突破": {
        "title": "爆量長紅",
        "simple": "人氣爆棚的大漲。",
        "detail": "成交量突然變得很大（爆量），且收盤收在最高點附近（長紅）。代表主力或大戶強力買進，不計成本就是要買，後市通常看好。"
    },
    "低檔爆量承接": {
        "title": "低檔爆量",
        "simple": "有人在低點大量撿便宜。",
        "detail": "股價在低檔，但成交量突然放大。這通常代表有人（可能是大戶）正在默默吃貨，等到籌碼收集完成，股價可能就會反轉向上。"
    },
    "量價齊揚": {
        "title": "量價齊揚",
        "simple": "價格漲，量也跟著增加，健康的漲勢。",
        "detail": "上漲需要動能（成交量），有量的上漲才走得久。如果漲卻沒量（量價背離），很容易掉下來。"
    },
    "RSI超賣背離": {
        "title": "RSI 低檔背離",
        "simple": "股價雖創新低，但指標沒創新低，賣壓竭盡。",
        "detail": "這是一個精準的抄底訊號。代表雖然價格還在跌，但內部的下跌動能已經在減弱，隨時準備強彈。"
    },
    "KD指標低檔鈍化": {
        "title": "KD 低檔鈍化 (或黃金交叉)",
        "simple": "股價超跌，隨時準備反彈。",
        "detail": "KD值長期在 20 以下，代表市場過度悲觀。一旦出現轉折（如黃金交叉），反彈力道通常很強。"
    },
    "回測支撐有守": {
        "title": "回測支撐有守",
        "simple": "跌不下去，買盤進場。",
        "detail": "股價跌到重要的支撐位（如月線或前波低點）就跌不下去了，代表這裡有強力買盤護盤。"
    },
    
    # ===== 營收相關術語 =====
    "營收年增率": {
        "title": "營收年增率 (YoY)",
        "simple": "今年跟去年同期比，賺多還是賺少。",
        "detail": "Year-over-Year，比較「今年這個月」與「去年同月」的營收差異。如果 YoY > 0，代表公司生意越做越好；如果 YoY < 0，代表衰退。"
    },
    "營收月增率": {
        "title": "營收月增率 (MoM)",
        "simple": "這個月跟上個月比，賺多還是賺少。",
        "detail": "Month-over-Month，比較「這個月」與「上個月」的營收差異。MoM 容易受季節性影響（如過年檔期、旺季淡季），所以要搭配 YoY 一起看。"
    },
    "營收爆發式成長": {
        "title": "營收爆發式成長",
        "simple": "公司業績大爆發，年增率超過 100%。",
        "detail": "營收年增率 (YoY) 超過 100%，代表營收翻倍成長。通常是因為新產品大賣、新客戶訂單、產業趨勢轉強等原因。這種爆發式成長如果能持續，股價通常會有大行情。"
    },
    "營收連三月成長": {
        "title": "營收連續成長",
        "simple": "公司業績穩定向上。",
        "detail": "營收連續多個月保持年增率 > 0，代表公司的成長趨勢穩定，不是曇花一現。連續成長的公司，獲利通常也會跟著成長。"
    },
    "營收穩健成長": {
        "title": "營收穩健成長",
        "simple": "公司業績持續成長，但速度溫和。",
        "detail": "營收年增率 (YoY) 在 20%-50% 之間，代表公司正在健康成長。雖然不如爆發式成長刺激，但這種穩健型成長通常更持久，風險較低。"
    },
    "營收大幅衰退": {
        "title": "營收大幅衰退",
        "simple": "⚠️ 公司業績下滑嚴重，需留意風險。",
        "detail": "營收年增率 (YoY) < -20%，代表公司生意比去年同期少了兩成以上。可能是產業景氣轉差、競爭加劇、客戶流失等原因。這時候要小心獲利能力也會受影響。"
    }
}

def get_glossary(term: str) -> dict:
    """根據術語取得解釋，支援模糊比對"""
    if term in GLOSSARY:
        return GLOSSARY[term]
    
    # 嘗試部分匹配
    for key, value in GLOSSARY.items():
        if key in term:
            return value
            
    # 預設回傳
    return {
        "title": term,
        "simple": "這是一個專業的技術分析訊號。",
        "detail": "建議結合 K 線圖與成交量綜合判斷。通常正向理由代表多方強勢，反向理由代表需留意風險。"
    }

def generate_dynamic_explanation(term: str, metadata: dict) -> dict:
    """
    生成動態解釋 (結合數據佐證)
    """
    # 先取得基礎解釋
    base = get_glossary(term)
    
    # 若無 metadata，回傳靜態解釋
    if not metadata:
        return base
        
    dynamic_detail = ""
    
    # 根據不同術語，使用 metadata 填空
    if "W底" in term:
        if 'date1' in metadata:
            dynamic_detail = (
                f"這檔股票分別在 **{metadata.get('date1')} ($ {metadata.get('price1')})** "
                f"與 **{metadata.get('date2')} ($ {metadata.get('price2')})** 兩次測試低點都沒跌破，"
                f"形成紮實的雙腳。並於今日突破頸線 **$ {metadata.get('neckline')}**，"
                f"確認底部完成，是可以進場的訊號。"
            )
            
    elif "KD" in term and "鈍化" in term:
        if 'start_date' in metadata:
             dynamic_detail = (
                 f"從 **{metadata.get('start_date')}** 到 **{metadata.get('end_date')}** 這段期間，"
                 f"KD指標連續 **{metadata.get('days')}** 天都在 25 以下（最低來到 **{metadata.get('min_k')}**）。"
                 f"這代表市場已經過度悲觀很久了，隨時可能像彈簧一樣出現強烈反彈。"
             )
             
    elif "回測" in term and "有守" in term:
        if 'test_date' in metadata:
            dynamic_detail = (
                f"股價在 **{metadata.get('test_date')}** 回落測試 **{metadata.get('support_name')}** "
                f"的價位 **$ {metadata.get('support_price')}**，但是沒有跌破（收盤價 $ {metadata.get('close_price')}）。"
                f"這顯示該價位有特定買盤在防守，是相對安全的佈局點。"
            )
            
    elif "爆量長紅" in term:
        if 'vol_ratio' in metadata:
            dynamic_detail = (
                f"今天的成交量是平常的 **{metadata.get('vol_ratio')} 倍**，且股價大漲 **{metadata.get('change_pct')}%**。"
                f"這種「價量齊揚」的走勢，代表有大戶不計成本強力買進，後市通常仍有高點可期。"
            )
            
    elif "均線多頭" in term:
        if 'ma5' in metadata:
             dynamic_detail = (
                 f"目前的均線呈現完美的發散排列：\n"
                 f"• 短線成本 (MA5): **$ {metadata.get('ma5')}**\n"
                 f"• 中線成本 (MA20): **$ {metadata.get('ma20')}**\n"
                 f"• 長線成本 (MA60): **$ {metadata.get('ma60')}**\n"
                 f"短 > 中 > 長，代表短中長線的投資人全數獲利，上方沒有套牢賣壓，上漲阻力最小。"
             )

    elif "MACD" in term:
        if 'dif' in metadata:
             dynamic_detail = (
                 f"MACD 快線 (DIF: **{metadata.get('dif')}**) 剛剛向上穿過慢線 (Signal: **{metadata.get('signal')}**)。"
                 f"這個「黃金交叉」通常標誌著整理結束，股價重新轉強的起點。"
             )
    
    # ===== 營收動能 =====
    elif "營收" in term:
        if 'revenue_yoy' in metadata:
            yoy = metadata.get('revenue_yoy')
            mom = metadata.get('revenue_mom', 'N/A')
            
            if "爆發式成長" in term:
                dynamic_detail = (
                    f"這檔股票的營收年增率高達 **{yoy}**，等於營收翻倍成長！"
                    f"這種爆發式成長通常來自新產品大賣、重大訂單或產業趨勢轉強。"
                    f"如果能持續，股價通常還有更大的空間。"
                )
            elif "連三月成長" in term or "穩健成長" in term:
                dynamic_detail = (
                    f"這檔股票的營收年增率為 **{yoy}**，"
                    f"月增率為 **{mom}**。"
                    f"公司業績持續成長，顯示基本面紮實，是穩健投資的好標的。"
                )
            elif "衰退" in term:
                dynamic_detail = (
                    f"⚠️ 這檔股票的營收年增率為 **{yoy}**，代表業績大幅下滑。"
                    f"可能是產業景氣轉差或競爭加劇，投資前需特別留意風險。"
                )

    # 若有產生動態解釋，替換掉原本的靜態解釋
    if dynamic_detail:
        # Create a copy to avoid modifying global constant
        new_glossary = base.copy()
        new_glossary['detail'] = dynamic_detail
        return new_glossary
        
    return base
