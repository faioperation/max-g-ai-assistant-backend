import json

class ResultsFormatter:
    """Formats JSON search results (flights/hotels) into WhatsApp-friendly text blocks."""

    MAX_CHARS = 4000  # Meta supports ~4096, keeping it safe

    @staticmethod
    def _flatten_data(data, list_key):
        """Extracts a flat list of items from various response structures."""
        if isinstance(data, list):
            # If it's a list of dicts, and the first dict has the key, extract it
            if len(data) > 0 and isinstance(data[0], dict) and list_key in data[0]:
                return data[0][list_key]
            return data
        if isinstance(data, dict):
            if list_key in data:
                return data[list_key]
            # Maybe it's nested
            for val in data.values():
                if isinstance(val, list):
                    return val
        return []

    @classmethod
    def format_flights(cls, offers_input, **kwargs):
        """Formats flight offers into chunks, respecting character limits."""
        offers = cls._flatten_data(offers_input, "offers")
        if not offers:
            return ["No flight offers found."]

        chunks = []
        current_text = "✈️ *Flight Search Results*\n\n"
        total_count = len(offers)

        for idx, offer in enumerate(offers):
            # Format single offer
            item_text = cls._format_single_flight(idx + 1, offer)
            
            # If adding this item exceeds limit, push current chunk and start new one
            if len(current_text) + len(item_text) > cls.MAX_CHARS:
                chunks.append(current_text.strip())
                current_text = "✈️ *Flight Search Results (continued)*\n\n"
            
            current_text += item_text

        # Add footer to the last chunk
        current_text += f"\n_Total results: {total_count}_"
        chunks.append(current_text.strip())
        
        return chunks

    @staticmethod
    def _format_single_flight(num, offer):
        """Helper to format one flight offer."""
        offer_id = offer.get("offer_id")
        price = f"{offer.get('total_amount')} {offer.get('total_currency')}"
        carrier = offer.get("owner", {}).get("name", "Unknown Airline")
        
        text = f"*{num}. {carrier}* — {price}\n"
        
        for s in offer.get("slices", []):
            origin = s.get("origin", {}).get("city_name") or s.get("origin", {}).get("iata_city_code")
            dest = s.get("destination", {}).get("city_name") or s.get("destination", {}).get("iata_city_code")
            
            segments = s.get("segments", [])
            if segments:
                dep_time = segments[0].get("departing_at", "").replace("T", " ")
                arr_time = segments[-1].get("arriving_at", "").replace("T", " ")
                text += f"   • {origin} → {dest}\n"
                text += f"     🕒 {dep_time} - {arr_time}\n"
        
        text += f"   🆔 ID: `{offer_id}`\n\n"
        return text

    @classmethod
    def format_hotels(cls, results_input, **kwargs):
        """Formats hotel results into chunks, respecting character limits."""
        results = cls._flatten_data(results_input, "results")
        if not results:
            return ["No hotel results found."]

        chunks = []
        current_text = "🏨 *Hotel Search Results*\n\n"
        total_count = len(results)

        for idx, res in enumerate(results):
            item_text = cls._format_single_hotel(idx + 1, res)
            
            if len(current_text) + len(item_text) > cls.MAX_CHARS:
                chunks.append(current_text.strip())
                current_text = "🏨 *Hotel Search Results (continued)*\n\n"
            
            current_text += item_text

        current_text += f"\n_Total results: {total_count}_"
        chunks.append(current_text.strip())
        
        return chunks

    @staticmethod
    def _format_single_hotel(num, res):
        """Helper to format one hotel result."""
        acc = res.get("accommodation", {})
        name = acc.get("name")
        city = acc.get("location", {}).get("address", {}).get("city_name")
        price = f"{res.get('cheapest_rate_total_amount')} {res.get('cheapest_rate_currency')}"
        search_id = res.get("id")
        
        text = f"*{num}. {name}* ({city})\n"
        text += f"   💰 From {price}\n"
        text += f"   🆔 ID: `{search_id}`\n\n"
        return text
