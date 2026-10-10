"""In-memory booking system with availability check and duplicate prevention."""

class SlotAlreadyBookedError(RuntimeError):
    """Raised when a time slot is already reserved."""

class BookingSystem:
    def __init__(self):
        self.bookings: list[dict[str, object]] = []

    def create_booking(self, user_id: str, slot: str) -> dict[str, object]:
        if not user_id or not user_id.strip() or not slot or not slot.strip():
            raise ValueError("user_id and slot must be non-empty strings.")
        clean_user = user_id.strip()
        clean_slot = slot.strip()

        # Check availability
        if any(b["slot"] == clean_slot for b in self.bookings):
            raise SlotAlreadyBookedError(f"Slot '{clean_slot}' is already booked.")

        booking = {
            "id": len(self.bookings) + 1,
            "user_id": clean_user,
            "slot": clean_slot,
        }
        self.bookings.append(booking)
        return booking

    def list_bookings(self) -> list[dict[str, object]]:
        return list(self.bookings)
