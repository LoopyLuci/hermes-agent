(ns hermes.protocols
  "Cross-language protocols shared by Rust/Clojure/TypeScript/Python runtimes."
  (:require [clojure.string :as str]))

(defn checksum [path]
  (let [file (clojure.java.io/file path)]
    (when (.exists file)
      (let [digest (java.security.MessageDigest/getInstance "SHA-256")]
        (with-open [rdr (clojure.java.io/reader file)
                    is (.getInputStream (java.io.FileInputStream. file))]
          (let [buf (byte-array 8192)]
            (loop [read (.read is buf)]
              (when (pos? read)
                (.update digest buf 0 read)
                (recur (.read is buf))))
            (format "%064x" (BigInteger. 1 (.digest digest))))))))

(defn now-ms [] (quot (System/currentTimeMillis) 1))

(defn reload-id-gen []
  (let [seq (atom 0)]
    (fn []
      (swap! seq inc))))

(def reload-id (reload-id-gen))

(defprotocol HotReloadable
  (reload [this event]))

(defprotocol AgenticTaskProto
  (task-id [this])
  (task-status [this])
  (task-output [this]))
