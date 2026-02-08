import ghidra.program.model.listing.Program;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;

public class XrefExample {

    /**
     * Get all cross-references to a given address.
     */
    public Reference[] getXrefsTo(Program program, Address addr) {
        ReferenceManager refMgr = program.getReferenceManager();
        Reference[] refs = refMgr.getReferencesTo(addr);
        return refs;
    }

    /**
     * Get cross-references from a given address.
     */
    public Reference[] getXrefsFrom(Program program, Address addr) {
        ReferenceManager refMgr = program.getReferenceManager();
        Reference[] refs = refMgr.getReferencesFrom(addr);
        return refs;
    }
}
