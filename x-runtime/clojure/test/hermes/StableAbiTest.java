import java.lang.foreign.*;
import java.nio.file.*;

public class StableAbiTest {
    public static void main(String[] args) throws Exception {
        Path dll = Path.of("D:/Projects/HermesAgentExpansion/x-runtime/rust/target/release/hermes_runtime_abi.dll");
        Arena arena = Arena.ofAuto();
        SymbolLookup lookup = SymbolLookup.libraryLookup(dll, arena);
        System.out.println("lookup=" + lookup);
        System.out.println("java-foreign-available=true");

        // Verify expanded symbols are present
        boolean hasWorkerStatus = lookup.find("stable_abi_worker_status_default").isPresent();
        boolean hasCapability = lookup.find("stable_abi_capability_default").isPresent();
        System.out.println("worker_status_symbol=" + hasWorkerStatus);
        System.out.println("capability_symbol=" + hasCapability);
        if (!hasWorkerStatus || !hasCapability) {
            throw new IllegalStateException("expanded ABI symbols missing");
        }

        // Invoke manifest_size and manifest_default via native handles
        FunctionDescriptor sizeDescriptor = FunctionDescriptor.of(ValueLayout.JAVA_LONG);
        var sizeHandle = Linker.nativeLinker().downcallHandle(
            lookup.find("stable_abi_manifest_size").orElseThrow(),
            sizeDescriptor
        );
        long size;
        try { size = (long) sizeHandle.invoke(); } catch (Throwable t) { throw new RuntimeException(t); }
        System.out.println("manifest_size=" + size);
        if (size <= 0) throw new IllegalStateException("manifest size must be positive");

        MemorySegment out = arena.allocate(size);
        var defaultHandle = Linker.nativeLinker().downcallHandle(
            lookup.find("stable_abi_manifest_default").orElseThrow(),
            FunctionDescriptor.ofVoid(AddressLayout.ADDRESS)
        );
        try { defaultHandle.invokeExact(out); } catch (Throwable t) { throw new RuntimeException(t); }
        System.out.println("manifest_default=ok");

        long abiMajor = out.getAtIndex(ValueLayout.JAVA_LONG, 0);
        long abiMinor = out.getAtIndex(ValueLayout.JAVA_LONG, 1);
        long protocolMajor = out.getAtIndex(ValueLayout.JAVA_LONG, 4);
        long protocolMinor = out.getAtIndex(ValueLayout.JAVA_LONG, 5);
        long hotReload = out.getAtIndex(ValueLayout.JAVA_INT, 12);
        long durableAtomics = out.getAtIndex(ValueLayout.JAVA_INT, 13);
        long capabilityTokens = out.getAtIndex(ValueLayout.JAVA_INT, 14);

        System.out.println("abi_major=" + abiMajor);
        System.out.println("abi_minor=" + abiMinor);
        System.out.println("protocol_major=" + protocolMajor);
        System.out.println("protocol_minor=" + protocolMinor);
        System.out.println("hot_reload=" + hotReload);
        System.out.println("durable_atomics=" + durableAtomics);
        System.out.println("capability_tokens=" + capabilityTokens);
        if (abiMajor <= 0) throw new IllegalStateException("abi_version_major must be > 0");
        if (protocolMajor <= 0) throw new IllegalStateException("protocol_version_major must be > 0");
        if (hotReload != 1 || durableAtomics != 1 || capabilityTokens != 1) {
            throw new IllegalStateException("capabilities not populated");
        }

        MemorySegment ws = arena.allocate(24);
        var wsHandle = Linker.nativeLinker().downcallHandle(
            lookup.find("stable_abi_worker_status_default").orElseThrow(),
            FunctionDescriptor.ofVoid(AddressLayout.ADDRESS)
        );
        try { wsHandle.invokeExact(ws); } catch (Throwable t) { throw new RuntimeException(t); }
        int wsStatus = ws.getAtIndex(ValueLayout.JAVA_INT, 0);
        long wsReloads = ws.getAtIndex(ValueLayout.JAVA_LONG, 1);
        System.out.println("worker_status_code=" + wsStatus);
        System.out.println("worker_reloads_total=" + wsReloads);
        if (wsStatus != 0 || wsReloads != 0) throw new IllegalStateException("worker status default not zeroed");

        MemorySegment cap = arena.allocate(16);
        var capHandle = Linker.nativeLinker().downcallHandle(
            lookup.find("stable_abi_capability_default").orElseThrow(),
            FunctionDescriptor.ofVoid(AddressLayout.ADDRESS)
        );
        try { capHandle.invokeExact(cap); } catch (Throwable t) { throw new RuntimeException(t); }
        int capGranted = cap.getAtIndex(ValueLayout.JAVA_INT, 0);
        System.out.println("capability_granted=" + capGranted);
        if (capGranted != 0) throw new IllegalStateException("capability default not zeroed");
    }
}
