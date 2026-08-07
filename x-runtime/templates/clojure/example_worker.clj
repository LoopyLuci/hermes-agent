(ns hermes.worker.example
  (:require [clojure.data.json :as json]
            [clojure.java.io :as io]))

(defn write! [out msg]
  (.write out (str (json/write-str msg) "\n"))
  (.flush out))

(defn read-msg [in]
  (let [line (.readLine in)]
    (when line
      (json/read-str line :key-fn keyword))))

(defn -main [& _args]
  (let [in (io/reader System/in)
        out (io/writer System/out)
        handshake (read-msg in)]
    (write! out {:protocol_version "1.0"
                  :message_id (str (java.util.UUID/randomUUID))
                  :timestamp (System/currentTimeMillis)
                  :type "ready"
                  :worker_id (:worker_id handshake)
                  :status "healthy"
                  :features ["task.echo"]})
    (loop []
      (let [msg (read-msg in)]
        (when msg
          (case (:type msg)
            "task.submit" (write! out {:protocol_version "1.0"
                                       :message_id (str (java.util.UUID/randomUUID))
                                       :timestamp (System/currentTimeMillis)
                                       :type "task.result"
                                       :task_id (:task_id msg)
                                       :ok true
                                       :result {:echo (:params msg)}
                                       :latency_ms 1})
            "reload.request" (write! out {:protocol_version "1.0"
                                          :message_id (str (java.util.UUID/randomUUID))
                                          :timestamp (System/currentTimeMillis)
                                          :type "reload.completed"
                                          :reload_id (:reload_id msg)
                                          :status "active"
                                          :checksum (:checksum msg "")})
            "shutdown" (System/exit 0)
            (write! out {:protocol_version "1.0"
                         :message_id (str (java.util.UUID/randomUUID))
                         :timestamp (System/currentTimeMillis)
                         :type "error"
                         :error {:code "unknown" :message (str "unknown type " (:type msg))}}))
          (recur))))))
