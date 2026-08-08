(ns hermes.atomic-state
  "Atomic state store with compare-and-swap semantics."
  (:require [hermes.protocols :as p]))

(defn atomic-state [] (atom {}))

(defn put-state [store k v] (swap! store assoc k v))

(defn get-state [store k] (get @store k))

(defn cas-state [store k expected new]
  (let [current (get @store k)]
    (if (= current expected)
      (do
        (reset! store (if (some? new) (assoc @store k new) (dissoc @store k)))
        true)
      false)))
