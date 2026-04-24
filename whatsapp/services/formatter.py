import json


class ResultsFormatter:
    """Formats JSON search results (flights/hotels) into WhatsApp-friendly text blocks."""

    MAX_CHARS = 4000  # Meta supports ~4096, keeping it safe

    @staticmethod
    def _flatten_data(data, list_key):
        """Extracts a flat list of items from various response structures."""
        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict) and list_key in data[0]:
                return data[0][list_key]
            return data
        if isinstance(data, dict):
            if list_key in data:
                return data[list_key]
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
        header = "✈️ *Flight Search Results*\n\n"
        footer = "\n\n_Please send your choice (Flight/Hotel/Room ID) to proceed with booking._"
        current_text = header
        total_count = len(offers)

        for idx, offer in enumerate(offers):
            item_text = cls._format_single_flight(idx + 1, offer)

            if len(current_text) + len(item_text) + len(footer) > cls.MAX_CHARS:
                chunks.append(current_text.strip() + footer)
                current_text = header.replace("Results*", "Results (continued)*")

            current_text += item_text

        current_text += f"\n_Total results: {total_count}_"
        chunks.append(current_text.strip() + footer)

        return chunks

    @staticmethod
    def _format_single_flight(num, offer):
        """Helper to format one flight offer."""
        offer_id = offer.get("offer_id")
        price = f"{offer.get('total_amount')} {offer.get('total_currency')}"
        carrier = offer.get("owner", {}).get("name", "Unknown Airline")

        text = f"*{num}. {carrier}* — {price}\n"

        for s in offer.get("slices", []):
            origin = s.get("origin", {}).get("city_name") or s.get("origin", {}).get(
                "iata_city_code"
            )
            dest = s.get("destination", {}).get("city_name") or s.get(
                "destination", {}
            ).get("iata_city_code")

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
        header = "🏨 *Hotel Search Results*\n\n"
        footer = "\n\n_Please send your choice (Flight/Hotel/Room ID) to proceed with booking._"
        current_text = header
        total_count = len(results)

        for idx, res in enumerate(results):
            item_text = cls._format_single_hotel(idx + 1, res)

            if len(current_text) + len(item_text) + len(footer) > cls.MAX_CHARS:
                chunks.append(current_text.strip() + footer)
                current_text = header.replace("Results*", "Results (continued)*")

            current_text += item_text

        current_text += f"\n_Total results: {total_count}_"
        chunks.append(current_text.strip() + footer)

        return chunks

    @staticmethod
    def _format_single_hotel(num, res):
        """Helper to format one hotel result."""
        acc = res.get("accommodation", {})
        name = acc.get("name")
        city = acc.get("location", {}).get("address", {}).get("city_name")
        phone = acc.get("phone_number", "N/A")
        amenities = acc.get("amenities", "")
        price = f"{res.get('cheapest_rate_total_amount')} {res.get('cheapest_rate_currency')}"
        search_id = res.get("id")

        text = f"*{num}. {name}* ({city})\n"
        text += f"   📞 Phone: {phone}\n"
        if amenities:
            text += f"   ✨ {amenities[:150]}{'...' if len(amenities) > 150 else ''}\n"
        text += f"   💰 From {price}\n"
        text += f"   🆔 ID: `{search_id}`\n\n"
        return text

    @classmethod
    def format_hotel_rates(cls, data, **kwargs):
        """Formats hotel room rates into chunks."""
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        if isinstance(data, dict) and "accommodation" not in data:
            for v in data.values():
                if isinstance(v, dict) and "accommodation" in v:
                    data = v
                    break

        if not isinstance(data, dict):
            return ["Invalid hotel rates data format."]

        acc = data.get("accommodation", {})
        name = acc.get("name", "Unknown Hotel")
        addr = acc.get("location", {}).get("address", {})
        full_add = addr.get("line_one", "")
        check_in_info = acc.get("check_in_information", {})
        rooms = acc.get("rooms", [])

        if not rooms:
            return ["No rooms available for this hotel."]

        chunks = []
        header = f"🛌 *Hotel Room Lists: {name}*\n"
        header += f"📍 Location: {full_add}\n"
        header += f"🕒 Check-in: {check_in_info.get('check_in_after_time', 'N/A')} | Check-out: {check_in_info.get('check_out_before_time', 'N/A')}\n\n"
        footer = "\n\n_Please send your choice (Flight/Hotel/Room ID) to proceed with booking._"

        current_text = header

        for room in rooms:
            room_name = room.get("name")
            beds_list = [
                f"{b.get('type')} - {b.get('count')}" for b in room.get("beds", [])
            ]
            beds_str = ", ".join(beds_list)

            for rate in room.get("rates", []):
                item_text = f"🏨 *Room: {room_name}*\n"
                item_text += f"   🛏 Beds: {beds_str}\n"
                item_text += f"   📦 Available: {rate.get('quantity_available')}\n"
                item_text += f"   🍽 Board: {rate.get('board_type')}\n"
                item_text += f"   💰 Price: {rate.get('total_amount')} {rate.get('total_currency')}\n"
                item_text += f"   📝 Conditions: {rate.get('conditions')}\n"
                item_text += f"   🆔 ID: `{rate.get('id')}`\n\n"

                if len(current_text) + len(item_text) + len(footer) > cls.MAX_CHARS:
                    chunks.append(current_text.strip() + footer)
                    current_text = header + "*(continued)*\n\n"

                current_text += item_text

        chunks.append(current_text.strip() + footer)
        return chunks
