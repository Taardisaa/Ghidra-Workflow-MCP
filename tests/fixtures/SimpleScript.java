import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Listing;

public class SimpleScript extends GhidraScript {

    /**
     * List all functions in the current program and print their names.
     */
    @Override
    public void run() throws Exception {
        Listing listing = currentProgram.getListing();
        FunctionIterator functions = listing.getFunctions(true);
        while (functions.hasNext()) {
            Function func = functions.next();
            String name = func.getName();
            println("Function: " + name + " at " + func.getEntryPoint());
        }
    }
}
