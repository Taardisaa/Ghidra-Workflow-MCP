import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Program;
import ghidra.program.model.address.Address;
import ghidra.util.task.TaskMonitor;

public class DecompileExample {

    /**
     * Decompile a function at the given address and return the C code.
     */
    public String decompileFunction(Program program, Address addr) {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(program);
        Function func = program.getListing().getFunctionAt(addr);
        DecompileResults res = ifc.decompileFunction(func, 30, TaskMonitor.DUMMY);
        if (res.decompileCompleted()) {
            String cCode = res.getDecompiledFunction().getC();
            ifc.dispose();
            return cCode;
        }
        ifc.dispose();
        return null;
    }
}
