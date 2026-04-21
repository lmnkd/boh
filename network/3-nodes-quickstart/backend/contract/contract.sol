// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.8.0 <0.9.0;

contract HealthDataValidator {

    enum Status { PENDING, APPROVED, REJECTED }

    struct Visit {
        address doctor;
        address patient;      // ✅ FIX
        bytes32 patientId;    // ✅ FIX
        bytes32 dataHash;     // ✅ FIX
        bool confirmed;
    }

    struct Record {
        uint256 visitId;
        address authority;
        bytes32 patientId;
        bytes32 dataHash;
        Status status;
        uint256 approveVotes;
        uint256 rejectVotes;
        mapping(address => bool) voted;
    }

    struct Probability {
        uint256 recordId;
        uint256 prior;
        uint256 posterior;
        uint256 updatedAt;
    }

    address public owner;

    mapping(address => bool) public isValidator;
    mapping(address => bool) public isDoctor;
    mapping(address => bool) public isAuthority;
    mapping(address => bool) public isOracle;
    mapping(address => bool) public isPatient;

    address[] private _validators;

    uint256 public visitCount;
    uint256 public recordCount;
    uint256 public probabilityCount;

    mapping(uint256 => Visit) private _visits;
    mapping(uint256 => Record) private _records;
    mapping(uint256 => Probability) private _probabilities;

    // ✅ nuovo
    mapping(uint256 => bool) public visitHasRecord;

    // EVENTI
    event VisitSubmitted(uint256 visitId, address doctor, address patient);
    event VisitConfirmed(uint256 visitId, address patient);
    event RecordProposed(uint256 recordId, uint256 visitId);
    event VoteCast(uint256 recordId, address voter, bool approve);
    event RecordFinalized(uint256 recordId, Status status);
    event ProbabilityUpdated(uint256 probId, uint256 recordId);

    modifier onlyOwner() { require(msg.sender == owner); _; }
    modifier onlyDoctor() { require(isDoctor[msg.sender]); _; }
    modifier onlyAuthority() { require(isAuthority[msg.sender]); _; }
    modifier onlyOracle() { require(isOracle[msg.sender]); _; }
    modifier onlyPatient() { require(isPatient[msg.sender]); _; }
    modifier onlyValidator() { require(isValidator[msg.sender]); _; }

    constructor(address[] memory validators) {
        owner = msg.sender;
        for (uint i = 0; i < validators.length; i++) {
            isValidator[validators[i]] = true;
            _validators.push(validators[i]);
        }
    }

    // RUOLI
    function addDoctor(address a) external onlyOwner { isDoctor[a] = true; }
    function addAuthority(address a) external onlyOwner { isAuthority[a] = true; }
    function addOracle(address a) external onlyOwner { isOracle[a] = true; }
    function addPatient(address a) external onlyOwner { isPatient[a] = true; }

    // STEP 1
    function submitVisit(
        address patient,
        bytes32 patientId,
        bytes32 dataHash
    ) external onlyDoctor returns (uint256 visitId) {

        visitCount++;
        visitId = visitCount;
        _visits[visitId] = Visit({
            doctor: msg.sender,
            patient: patient,
            patientId: patientId,
            dataHash: dataHash,
            confirmed: false
        });

        emit VisitSubmitted(visitId, msg.sender, patient);
    }

    // STEP 2
    function confirmVisit(uint256 visitId) external onlyPatient {
        Visit storage v = _visits[visitId];

        require(msg.sender == v.patient, "Non sei il paziente"); // ✅ FIX
        require(!v.confirmed, "Gia confermata");

        v.confirmed = true;

        emit VisitConfirmed(visitId, msg.sender);
    }

    // STEP 3
    function proposeRecord(uint256 visitId, bytes32 dataHash)
        external onlyAuthority returns (uint256 recordId)
    {
        require(_visits[visitId].confirmed, "Non confermata");
        require(!visitHasRecord[visitId], "Gia esiste record"); // ✅ FIX

        recordCount++;
        recordId = recordCount;

        Record storage r = _records[recordId];

        r.visitId = visitId;
        r.authority = msg.sender;
        r.patientId = _visits[visitId].patientId;
        r.dataHash = dataHash;
        r.status = Status.PENDING;

        visitHasRecord[visitId] = true;

        emit RecordProposed(recordId, visitId);
    }

    // STEP 4
    function vote(uint256 recordId, bool approve) external onlyValidator {
        Record storage r = _records[recordId];

        require(!r.voted[msg.sender], "Gia votato");
        require(r.status == Status.PENDING, "Finalizzato");

        r.voted[msg.sender] = true;

        if (approve) r.approveVotes++;
        else r.rejectVotes++;

        uint256 majority = _validators.length / 2 + 1;

        if (r.approveVotes >= majority) {
            r.status = Status.APPROVED;
            emit RecordFinalized(recordId, Status.APPROVED);
        } else if (r.rejectVotes >= majority) {
            r.status = Status.REJECTED;
            emit RecordFinalized(recordId, Status.REJECTED);
        }

        emit VoteCast(recordId, msg.sender, approve);
    }

    // STEP 5
    function updateProbability(
        uint256 recordId,
        uint256 prior,
        uint256 posterior
    ) external onlyOracle returns (uint256 probId) {

        require(_records[recordId].status == Status.APPROVED);

        probabilityCount++;
        probId = probabilityCount;

        _probabilities[probId] = Probability(
            recordId,
            prior,
            posterior,
            block.timestamp
        );

        emit ProbabilityUpdated(probId, recordId);
    }
}