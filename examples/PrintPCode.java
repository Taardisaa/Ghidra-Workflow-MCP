// Print P-code operations for a function using the decompiler's high-level representation.
// @category Analysis
// @author ghidra-workflow

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.pcode.HighFunction;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.PcodeOpAST;
import ghidra.program.model.pcode.Varnode;

import java.util.Iterator;
import java.util.List;

public class PrintPCode extends GhidraScript {

    @Override
    protected void run() throws Exception {
        String name = askString("Function Name", "Enter the function name:");

        List<Function> functions = getGlobalFunctions(name);
        if (functions.isEmpty()) {
            println("No function found with name: " + name);
            return;
        }

        DecompInterface decompiler = new DecompInterface();
        DecompileOptions options = new DecompileOptions();
        decompiler.setOptions(options);
        decompiler.toggleSyntaxTree(true);
        decompiler.openProgram(currentProgram);

        try {
            for (Function func : functions) {
                monitor.checkCancelled();

                DecompileResults results =
                    decompiler.decompileFunction(func, decompiler.getOptions().getDefaultTimeout(), monitor);

                HighFunction highFunc = results.getHighFunction();
                if (highFunc == null) {
                    println("Failed to decompile: " + func.getName());
                    continue;
                }

                println("=== P-Code for: " + func.getName() + " @ " + func.getEntryPoint() + " ===");

                Iterator<PcodeOpAST> opIter = highFunc.getPcodeOps();
                int index = 0;
                while (opIter.hasNext()) {
                    monitor.checkCancelled();
                    PcodeOpAST op = opIter.next();

                    StringBuilder sb = new StringBuilder();
                    sb.append(String.format("[%4d] ", index));

                    // Output varnode
                    Varnode output = op.getOutput();
                    if (output != null) {
                        sb.append(formatVarnode(output));
                        sb.append(" = ");
                    }

                    // Mnemonic
                    sb.append(op.getMnemonic());

                    // Input varnodes
                    for (int i = 0; i < op.getNumInputs(); i++) {
                        Varnode input = op.getInput(i);
                        if (input != null) {
                            sb.append(i == 0 ? " " : ", ");
                            sb.append(formatVarnode(input));
                        }
                    }

                    println(sb.toString());
                    index++;
                }

                println("=== Total P-Code ops: " + index + " ===\n");
            }
        } finally {
            decompiler.dispose();
        }
    }

    private String formatVarnode(Varnode vn) {
        if (vn.isConstant()) {
            return "0x" + Long.toHexString(vn.getOffset());
        }
        if (vn.isAddress()) {
            return "ram[" + vn.getAddress() + "]";
        }
        if (vn.isUnique()) {
            return "u_" + Long.toHexString(vn.getOffset()) + ":" + vn.getSize();
        }
        if (vn.isRegister()) {
            return currentProgram.getRegister(vn.getAddress(), vn.getSize()) != null
                ? currentProgram.getRegister(vn.getAddress(), vn.getSize()).getName()
                : "reg[" + vn.getAddress() + "]";
        }
        return vn.toString();
    }
}
