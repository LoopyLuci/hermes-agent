import java.lang.foreign.*;
import java.nio.file.*;

public class StableAbiTest {
    public static void main(String[] args) throws Exception {
        var dll = Path.of("D:/Projects/HermesAgentExpansion/x-runtime/rust/target/release/hermes_runtime_abi.dll");
        SymbolLookup lookup = SymbolLookup.libraryLookup(dll, Arena.globalScope());
        System.out.println("lookup=" + lookup);
        System.out.println("ok");
    }
}
