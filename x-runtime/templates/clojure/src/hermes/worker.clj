(ns hermes.worker
  (:require [clojure.data.json :as json]))

(defn checksum [path]
  (let [bytes (.getBytes (slurp path))
        md  (java.security.MessageDigest/getInstance "MD5")]
    (.update md bytes)
    (let [digest (.digest md)]
      (apply str (map #(format "%02x" (bit-and % 0xff)) digest)))))

(defn validate [path]
  (try
    (load-file path)
    true
    (catch Exception _ false)))

(defn shadow-apply [path content]
  (let [target  (java.io.File. path)
        dir     (.getParentFile target)
        base    (.getName target)
        tmp     (java.io.File. dir (str base ".reload-" (System/currentTimeMillis) ".clj"))]
    (spit tmp content)
    [(.getAbsolutePath tmp) (checksum tmp)]))

(defn handle-reload [envelope]
  (let [path      (:path envelope)
        checksum  (:checksum envelope)
        reload-id (:reload_id envelope)]
    (cond
      (nil? path)
      {:type "reload.completed" :reload_id reload-id :status "failed" :error {:message "missing path"}}

      (nil? checksum)
      {:type "reload.completed" :reload_id reload-id :status "failed" :error {:message "missing checksum"}}

      :else
      (let [file (java.io.File. path)]
        (if (.exists file)
          (if (= (checksum path) checksum)
            {:type "reload.completed" :reload_id reload-id :status "completed" :checksum checksum}
            (let [content (slurp path)
                  [shadow shadow-csum] (shadow-apply path content)]
              (if (validate shadow)
                (let [tmp (java.io.File. (str path ".tmp"))]
                  (spit tmp content)
                  (.renameTo tmp file)
                  {:type "reload.completed" :reload_id reload-id :status "completed" :checksum checksum})
                {:type "reload.completed" :reload_id reload-id :status "failed" :error {:message "shadow validation failed"}})))
          {:type "reload.completed" :reload_id reload-id :status "failed" :error {:message (str "missing file: " path)}})))))

(defn handle-message [line]
  (let [envelope (json/read-str line :key-fn keyword)]
    (case (:type envelope)
      "reload.request" (handle-reload envelope)
      "task.submit"    {:type "task.result" :task_id (:task_id envelope) :ok true :result {:echo (:params envelope)} :latency_ms 1}
      "shutdown"       {:type "shutdown" :grace_ms 5000}
      {:type "error" :error {:code "unknown" :message (str "unknown type: " (:type envelope))}})))

(defn -main [& args]
  (println (json/write-str {:type "ready" :worker_id "clojure-worker" :status "healthy" :features ["task.echo"]}))
  (doseq [line (line-seq (java.io.BufferedReader. *in*))]
    (when (clojure.string/blank? line)
      (println (json/write-str (handle-message line))))))
