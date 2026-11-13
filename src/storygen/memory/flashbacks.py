"""Flashbacks (STORY-TIME): a flashback adds facts to memory and nothing else."""
from .journal import MemoryJournal, replay_memory

FLASHBACK_FACTS_ONLY='Спогад додає лише факти'


def check_flashback_journal(journal: MemoryJournal, previous: MemoryJournal) -> None:
    """A flashback journal keeps every record of the previous memory as it was; its new records are facts only."""
    old,new=replay_memory(previous),replay_memory(journal)
    if any(new.get(claim_id)!=record for claim_id,record in old.items()) or any(
            record.category!='facts' for claim_id,record in new.items() if claim_id not in old):
        raise ValueError(FLASHBACK_FACTS_ONLY)
