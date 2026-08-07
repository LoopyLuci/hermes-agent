(ns hermes.agentic
  "Agentic task queue/runtime."
  (:require [hermes.protocols :as p]
            [clojure.core.async :as async]))

(defn task [owner kind input]
  {:id (format "task-%s" (java.util.UUID/randomUUID))
   :owner owner
   :kind kind
   :input input
   :output nil
   :status :queued
   :created-at (p/now-ms)
   :updated-at (p/now-ms)})
