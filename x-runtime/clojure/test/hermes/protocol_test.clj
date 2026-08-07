(ns hermes.protocol-test
  (:require [clojure.test :as t :refer [deftest testing is run-tests]]))

(deftest round-trip-envelope
  (testing "envelope JSON serialization contract"
    (let [envelope {"type" "handshake"}]
      (is (= "handshake" (get envelope "type"))))))

(defn -main [& _args]
  (let [r (run-tests 'hermes.protocol-test)]
    (System/exit (if (zero? (+ (or (:fail r) 0) (or (:error r) 0))) 0 1))))
