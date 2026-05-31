// Package main is a controlled lineage-break benchmark seed for the full-audit
// SCA path. It pins three Go modules at OLD, vulnerable-by-design versions and
// deliberately splits their vulnerable symbols into two groups:
//
//   REACHABLE  (govulncheck WILL report — the vulnerable symbol is actually called):
//     - github.com/dgrijalva/jwt-go  MapClaims.VerifyAudience  (GO-2020-0017 / CVE-2020-26160)
//         reached via jwt.Parse -> Claims.Valid -> MapClaims.VerifyAudience
//     - golang.org/x/text/language   ParseAcceptLanguage       (GO-2022-1059 / CVE-2022-32149
//                                                                AND GO-2021-0113 / CVE-2021-38561;
//                                                                both advisories list ParseAcceptLanguage)
//
//   UNREACHABLE (imported but the vulnerable symbol is NOT called -> govulncheck stays
//   silent -> honest false negative against the full osv.dev ground truth):
//     - golang.org/x/text/encoding/unicode + transform  (GO-2020-0015 / CVE-2020-14040):
//         we import x/text only for the `language` package; the vulnerable
//         unicode/transform decode path is never invoked.
//     - github.com/gogo/protobuf  plugin/unmarshal       (GO-2021-0053 / CVE-2021-3121):
//         we import gogo's `proto` runtime package and call a benign symbol; the
//         vulnerable code-generator symbol (unmarshal.Generate / unmarshal.field)
//         is never on any call path from this binary.
//
// `go build ./...` must pass. This is not a real application.
package main

import (
	"fmt"

	jwt "github.com/dgrijalva/jwt-go"
	"github.com/gogo/protobuf/proto"
	"golang.org/x/text/language"
)

// parseToken reaches jwt-go's MapClaims.VerifyAudience (the CVE-2020-26160 symbol):
// jwt.Parse validates the claims, and for MapClaims that calls VerifyAudience.
func parseToken(tokenString string) {
	token, _, err := new(jwt.Parser).ParseUnverified(tokenString, jwt.MapClaims{})
	if err != nil {
		fmt.Println("parse error:", err)
		return
	}
	if claims, ok := token.Claims.(jwt.MapClaims); ok {
		// Directly exercise the vulnerable audience-verification symbol.
		ok := claims.VerifyAudience("expected-audience", false)
		fmt.Println("audience ok:", ok)
	}
}

// matchLanguage reaches x/text language.ParseAcceptLanguage (the CVE-2022-32149 and
// CVE-2021-38561 symbol). Both advisories list ParseAcceptLanguage as vulnerable.
func matchLanguage(header string) {
	tags, _, err := language.ParseAcceptLanguage(header)
	if err != nil {
		fmt.Println("accept-language parse error:", err)
		return
	}
	fmt.Println("parsed tags:", tags)
}

// useProtoBenign imports gogo/protobuf but only touches a benign runtime symbol.
// The vulnerable symbol (plugin/unmarshal) is a code-generator path, never reached
// from this binary -> CVE-2021-3121 is present-but-unreachable -> honest FN.
func useProtoBenign() {
	// proto.String is a trivial helper; it does NOT pull in plugin/unmarshal.
	s := proto.String("benign")
	fmt.Println("proto helper:", *s)
}

func main() {
	parseToken("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJzb21lLWF1ZCJ9.sig")
	matchLanguage("en-US,en;q=0.9,fr;q=0.8")
	useProtoBenign()
}
