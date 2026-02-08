// Decompile a function by name and print the C code.
// @category Analysis
// @author ghidra-workflow

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;

import java.util.List;

public class DecompileByName extends GhidraScript {

    @Override
    protected void run() throws Exception {
        String name = askString("Function Name", "Enter the function name to decompile:");

        // Find functions matching the name
        List<Function> functions = getGlobalFunctions(name);
        if (functions.isEmpty()) {
            println("No function found with name: " + name);
            return;
        }

        // Set up the decompiler
        DecompInterface decompiler = new DecompInterface();
        DecompileOptions options = new DecompileOptions();
        decompiler.setOptions(options);
        decompiler.toggleCCode(true);
        decompiler.toggleSyntaxTree(false);
        decompiler.setSimplificationStyle("decompile");
        decompiler.openProgram(currentProgram);

        try {
            for (Function func : functions) {
                monitor.checkCancelled();

                println("=== Decompiling: " + func.getName() + " @ " + func.getEntryPoint() + " ===");

                DecompileResults results =
                    decompiler.decompileFunction(func, decompiler.getOptions().getDefaultTimeout(), monitor);

                if (results.getDecompiledFunction() != null) {
                    println(results.getDecompiledFunction().getC());
                } else {
                    println("Decompilation failed for " + func.getName());
                }
            }
        } finally {
            decompiler.dispose();
        }
    }
}
