(ns hermes.core
  "Hermes Agent Clojure runtime integration point."
  (:require [hermes.atomic-state :as atomic-state]
            [hermes.agentic :as agentic]
            [clojure.java.io :as io]))

(defn init! []
  (println "[hermes.clj] runtime initialized"))

(defn reload-module [path]
  (let [cksum (hermes.protocols/checksum path)]
    (println "[hermes.clj] hot reload requested:" path "checksum:" cksum)
    cksum))
