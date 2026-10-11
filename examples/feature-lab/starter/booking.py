"""In-memory booking system without conflict detection (starter)."""

class BookingSystem:
    def __init__(self):
        self.bookings: list[dict[str, object]] = []

    def create_booking(self, user_id: str, slot: str) -> dict[str, object]:
        if not user_id or not slot:
            raise ValueError("user_id and slot are required.")
        booking = {
            "id": len(self.bookings) + 1,
            "user_id": user_id.strip(),
            "slot": slot.strip(),
        }
        self.bookings.append(booking)
        return booking

    def list_bookings(self) -> list[dict[str, object]]:
        return list(self.bookings)
