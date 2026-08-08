import java.lang.foreign.*;
import java.util.*;
public class ListForeign {
    public static void main(String[] args) {
        System.out.println("packages:");
        System.out.println(FunctionDescriptor.class.getPackage());
        System.out.println("class=" + FunctionDescriptor.class.getName());
        System.out.println("linker=" + Linker.class.getName());
        System.out.println("symbol=" + SymbolLookup.class.getName());
        System.out.println("segment=" + Arena.class.getName());
        System.out.println("value=" + ValueLayout.class.getName());
    }
}
